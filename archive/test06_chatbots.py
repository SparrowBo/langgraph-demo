from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
import config as cfg
import os
from exa_py import Exa
from datetime import datetime
from components.tools.chatbots_tools.main_tool import (
    init_and_get_tools,
    create_tool_node_with_fallback,
)
from langchain_core.messages import ToolMessage

# from langgraph.checkpoint.memory import MemorySaver
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from typing import Callable


from typing import Any, Optional

# 假设 State, StateGraph, etc. 已经被正确导入
def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_info: str
    dialog_state: Annotated[
        list[
            Literal[
                "assistant",
                "update_flight",
                "book_car_rental",
                "book_hotel",
                "book_excursion",
            ]
        ],
        update_dialog_stack,
    ]


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            result = self.runnable.invoke(state)
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}


class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the main assistant,
    who can re-route the dialog based on the user's needs."""

    cancel: bool = True
    reason: str

    class Config:
        json_schema_extra = {
            "example": {
                "cancel": True,
                "reason": "User changed their mind about the current task.",
            },
            "example 2": {
                "cancel": True,
                "reason": "I have fully completed the task.",
            },
            "example 3": {
                "cancel": False,
                "reason": "I need to search the user's emails or calendar for more information.",
            },
        }


# Primary Assistant
class ToFlightBookingAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle flight updates and cancellations."""

    request: str = Field(
        description="Any necessary follow-up questions the update flight assistant should clarify before proceeding."
    )


class ToBookCarRental(BaseModel):
    """Transfers work to a specialized assistant to handle car rental bookings."""

    location: str = Field(
        description="The location where the user wants to rent a car."
    )
    start_date: str = Field(description="The start date of the car rental.")
    end_date: str = Field(description="The end date of the car rental.")
    request: str = Field(
        description="Any additional information or requests from the user regarding the car rental."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "Basel",
                "start_date": "2023-07-01",
                "end_date": "2023-07-05",
                "request": "I need a compact car with automatic transmission.",
            }
        }


class ToHotelBookingAssistant(BaseModel):
    """Transfer work to a specialized assistant to handle hotel bookings."""

    location: str = Field(
        description="The location where the user wants to book a hotel."
    )
    checkin_date: str = Field(description="The check-in date for the hotel.")
    checkout_date: str = Field(description="The check-out date for the hotel.")
    request: str = Field(
        description="Any additional information or requests from the user regarding the hotel booking."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "Zurich",
                "checkin_date": "2023-08-15",
                "checkout_date": "2023-08-20",
                "request": "I prefer a hotel near the city center with a room that has a view.",
            }
        }


class ToBookExcursion(BaseModel):
    """Transfers work to a specialized assistant to handle trip recommendation and other excursion bookings."""

    location: str = Field(
        description="The location where the user wants to book a recommended trip."
    )
    request: str = Field(
        description="Any additional information or requests from the user regarding the trip recommendation."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "Lucerne",
                "request": "The user is interested in outdoor activities and scenic views.",
            }
        }


# 创建一个类来封装静态组件的初始化
class GraphBuilder:
    def __init__(self, init_db=True):
        # 初始化与 stream_handler 无关的部分
        self.init_tools(init_db)
        self.init_prompts()
        self.init_static_variables()

    def init_tools(self, init_db):
        (
            self.lookup_policy,
            self.search_trip_recommendations,
            self.book_excursion,
            self.update_excursion,
            self.cancel_excursion,
            self.fetch_user_flight_information,
            self.search_flights,
            self.update_ticket_to_new_flight,
            self.cancel_ticket,
            self.search_hotels,
            self.book_hotel,
            self.update_hotel,
            self.cancel_hotel,
            self.search_car_rentals,
            self.book_car_rental,
            self.update_car_rental,
            self.cancel_car_rental,
        ) = init_and_get_tools(init_db)

    def init_prompts(self):
        self.flight_booking_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a specialized assistant for handling flight updates. "
                    "The primary assistant delegates work to you whenever the user needs help updating their bookings. "
                    "Confirm the updated flight details with the customer and inform them of any additional fees. "
                    "When searching, be persistent. Expand your query bounds if the first search returns no results. "
                    "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
                    "Remember that a booking isn't completed until after the relevant tool has successfully been used."
                    "\n\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
                    "\nCurrent time: {time}."
                    "\n\nIf the user needs help, and none of your tools are appropriate for it, then"
                    ' "CompleteOrEscalate" the dialog to the host assistant. Do not waste the user\'s time. Do not make up invalid tools or functions.',
                ),
                ("placeholder", "{messages}"),
            ]
        ).partial(time=datetime.now())

        self.book_hotel_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a specialized assistant for handling hotel bookings. "
                    "The primary assistant delegates work to you whenever the user needs help booking a hotel. "
                    "Search for available hotels based on the user's preferences and confirm the booking details with the customer. "
                    "When searching, be persistent. Expand your query bounds if the first search returns no results. "
                    "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
                    "Remember that a booking isn't completed until after the relevant tool has successfully been used."
                    "\nCurrent time: {time}."
                    '\n\nIf the user needs help, and none of your tools are appropriate for it, then "CompleteOrEscalate" the dialog to the host assistant.'
                    " Do not waste the user's time. Do not make up invalid tools or functions."
                    "\n\nSome examples for which you should CompleteOrEscalate:\n"
                    " - 'what's the weather like this time of year?'\n"
                    " - 'nevermind i think I'll book separately'\n"
                    " - 'i need to figure out transportation while i'm there'\n"
                    " - 'Oh wait i haven't booked my flight yet i'll do that first'\n"
                    " - 'Hotel booking confirmed'",
                ),
                ("placeholder", "{messages}"),
            ]
        ).partial(time=datetime.now())

        self.book_car_rental_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a specialized assistant for handling car rental bookings. "
                    "The primary assistant delegates work to you whenever the user needs help booking a car rental. "
                    "Search for available car rentals based on the user's preferences and confirm the booking details with the customer. "
                    "When searching, be persistent. Expand your query bounds if the first search returns no results. "
                    "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
                    "Remember that a booking isn't completed until after the relevant tool has successfully been used."
                    "\nCurrent time: {time}."
                    "\n\nIf the user needs help, and none of your tools are appropriate for it, then "
                    '"CompleteOrEscalate" the dialog to the host assistant. Do not waste the user\'s time. Do not make up invalid tools or functions.'
                    "\n\nSome examples for which you should CompleteOrEscalate:\n"
                    " - 'what's the weather like this time of year?'\n"
                    " - 'What flights are available?'\n"
                    " - 'nevermind i think I'll book separately'\n"
                    " - 'Oh wait i haven't booked my flight yet i'll do that first'\n"
                    " - 'Car rental booking confirmed'",
                ),
                ("placeholder", "{messages}"),
            ]
        ).partial(time=datetime.now())

        self.book_excursion_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a specialized assistant for handling trip recommendations. "
                    "The primary assistant delegates work to you whenever the user needs help booking a recommended trip. "
                    "Search for available trip recommendations based on the user's preferences and confirm the booking details with the customer. "
                    "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
                    "When searching, be persistent. Expand your query bounds if the first search returns no results. "
                    "Remember that a booking isn't completed until after the relevant tool has successfully been used."
                    "\nCurrent time: {time}."
                    '\n\nIf the user needs help, and none of your tools are appropriate for it, then "CompleteOrEscalate" the dialog to the host assistant. Do not waste the user\'s time. Do not make up invalid tools or functions.'
                    "\n\nSome examples for which you should CompleteOrEscalate:\n"
                    " - 'nevermind i think I'll book separately'\n"
                    " - 'i need to figure out transportation while i'm there'\n"
                    " - 'Oh wait i haven't booked my flight yet i'll do that first'\n"
                    " - 'Excursion booking confirmed!'",
                ),
                ("placeholder", "{messages}"),
            ]
        ).partial(time=datetime.now())

        self.primary_assistant_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful customer support assistant for Swiss Airlines. "
                    "Your primary role is to search for flight information and company policies to answer customer queries. "
                    "If a customer requests to update or cancel a flight, book a car rental, book a hotel, or get trip recommendations, "
                    "delegate the task to the appropriate specialized assistant by invoking the corresponding tool. You are not able to make these types of changes yourself."
                    " Only the specialized assistants are given permission to do this for the user."
                    "The user is not aware of the different specialized assistants, so do not mention them; just quietly delegate through function calls. "
                    "Provide detailed information to the customer, and always double-check the database before concluding that information is unavailable. "
                    "When searching, be persistent. Expand your query bounds if the first search returns no results. "
                    "If a search comes up empty, expand your search before giving up."
                    "\n\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
                    "\nCurrent time: {time}.",
                ),
                ("placeholder", "{messages}"),
            ]
        ).partial(time=datetime.now())

    def init_static_variables(self):

        # 初始化工具列表
        self.update_flight_safe_tools = [self.search_flights]
        self.update_flight_sensitive_tools = [
            self.update_ticket_to_new_flight,
            self.cancel_ticket,
        ]
        self.update_flight_tools = (
            self.update_flight_safe_tools + self.update_flight_sensitive_tools
        )

        self.book_hotel_safe_tools = [self.search_hotels]
        self.book_hotel_sensitive_tools = [
            self.book_hotel,
            self.update_hotel,
            self.cancel_hotel,
        ]
        self.book_hotel_tools = (
            self.book_hotel_safe_tools + self.book_hotel_sensitive_tools
        )

        self.book_car_rental_safe_tools = [self.search_car_rentals]
        self.book_car_rental_sensitive_tools = [
            self.book_car_rental,
            self.update_car_rental,
            self.cancel_car_rental,
        ]
        self.book_car_rental_tools = (
            self.book_car_rental_safe_tools + self.book_car_rental_sensitive_tools
        )

        self.book_excursion_safe_tools = [self.search_trip_recommendations]
        self.book_excursion_sensitive_tools = [
            self.book_excursion,
            self.update_excursion,
            self.cancel_excursion,
        ]
        self.book_excursion_tools = (
            self.book_excursion_safe_tools + self.book_excursion_sensitive_tools
        )

        # 设置环境变量
        os.environ["AZURE_OPENAI_API_KEY"] = cfg.AZURE_OPENAI_API_KEY
        os.environ["AZURE_OPENAI_ENDPOINT"] = cfg.ENDPOINT_URL
        os.environ["LANGCHAIN_TRACING_V2"] = cfg.LANGCHAIN_TRACING_V2
        os.environ["LANGCHAIN_ENDPOINT"] = cfg.LANGCHAIN_ENDPOINT
        os.environ["LANGCHAIN_API_KEY"] = cfg.LANGCHAIN_API_KEY_2
        os.environ["LANGCHAIN_PROJECT"] = cfg.LANGCHAIN_PROJECT_2

        self.exa = Exa(api_key=cfg.EXA_API_KEY)

        @tool
        def search_and_contents(query: str):
            """Search for webpages based on the query and retrieve their contents."""
            # This combines two API endpoints: search and contents retrieval
            return self.exa.search_and_contents(
                query, use_autoprompt=True, num_results=1, text=True, highlights=True
            )

        self.primary_assistant_tools = [
            search_and_contents,
            self.search_flights,
            self.lookup_policy,
        ]

    def create_graph(self, stream_handler=None) -> StateGraph:
        # 创建依赖于 stream_handler 的部分
        llm = None
        if stream_handler is None:
            llm = AzureChatOpenAI(
                azure_deployment=cfg.DEPLOYMENT_NAME,
                api_version=cfg.AZURE_API_VERSION
            )
        else :
            llm = AzureChatOpenAI(
                azure_deployment=cfg.DEPLOYMENT_NAME,
                api_version=cfg.AZURE_API_VERSION,
                streaming=True,
                callbacks=[stream_handler],
            )

        # 定义运行实例（runnables）
        update_flight_runnable = self.flight_booking_prompt | llm.bind_tools(
            self.update_flight_tools + [CompleteOrEscalate]
        )

        book_hotel_runnable = self.book_hotel_prompt | llm.bind_tools(
            self.book_hotel_tools + [CompleteOrEscalate]
        )

        book_car_rental_runnable = self.book_car_rental_prompt | llm.bind_tools(
            self.book_car_rental_tools + [CompleteOrEscalate]
        )

        book_excursion_runnable = self.book_excursion_prompt | llm.bind_tools(
            self.book_excursion_tools + [CompleteOrEscalate]
        )

        assistant_runnable = self.primary_assistant_prompt | llm.bind_tools(
            self.primary_assistant_tools
            + [
                ToFlightBookingAssistant,
                ToBookCarRental,
                ToHotelBookingAssistant,
                ToBookExcursion,
            ]
        )

        def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
            def entry_node(state: State) -> dict:
                tool_call_id = state["messages"][-1].tool_calls[0]["id"]
                return {
                    "messages": [
                        ToolMessage(
                            content=f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                            f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                            " and the booking, update, or other action is not complete until after you have successfully invoked the appropriate tool."
                            " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                            " Do not mention who you are—just act as the proxy for the assistant.",
                            tool_call_id=tool_call_id,
                        )
                    ],
                    "dialog_state": new_dialog_state,
                }

            return entry_node

        # 构建图形
        builder = StateGraph(State)

        # 这里继续添加节点和边，使用上面定义的运行实例
        def user_info(state: State):
            return {"user_info": self.fetch_user_flight_information.invoke({})}

        builder.add_node("fetch_user_info", user_info)
        builder.add_edge(START, "fetch_user_info")

        # Flight booking assistant nodes and edges
        builder.add_node(
            "enter_update_flight",
            create_entry_node("Flight Updates & Booking Assistant", "update_flight"),
        )
        builder.add_node("update_flight", Assistant(update_flight_runnable))
        builder.add_edge("enter_update_flight", "update_flight")
        builder.add_node(
            "update_flight_sensitive_tools",
            create_tool_node_with_fallback(self.update_flight_sensitive_tools),
        )
        builder.add_node(
            "update_flight_safe_tools",
            create_tool_node_with_fallback(self.update_flight_safe_tools),
        )

        def route_update_flight(
            state: State,
        ):
            route = tools_condition(state)
            if route == END:
                return END
            tool_calls = state["messages"][-1].tool_calls
            did_cancel = any(
                tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls
            )
            if did_cancel:
                return "leave_skill"
            safe_toolnames = [t.name for t in self.update_flight_safe_tools]
            if all(tc["name"] in safe_toolnames for tc in tool_calls):
                return "update_flight_safe_tools"
            return "update_flight_sensitive_tools"

        builder.add_edge("update_flight_sensitive_tools", "update_flight")
        builder.add_edge("update_flight_safe_tools", "update_flight")
        builder.add_conditional_edges(
            "update_flight",
            route_update_flight,
            [
                "update_flight_sensitive_tools",
                "update_flight_safe_tools",
                "leave_skill",
                END,
            ],
        )

        # This node will be shared for exiting all specialized assistants
        def pop_dialog_state(state: State) -> dict:
            """Pop the dialog stack and return to the main assistant.

            This lets the full graph explicitly track the dialog flow and delegate control
            to specific sub-graphs.
            """
            messages = []
            if state["messages"][-1].tool_calls:
                # Note: Doesn't currently handle the edge case where the llm performs parallel tool calls
                messages.append(
                    ToolMessage(
                        content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                        tool_call_id=state["messages"][-1].tool_calls[0]["id"],
                    )
                )
            return {
                "dialog_state": "pop",
                "messages": messages,
            }

        builder.add_node("leave_skill", pop_dialog_state)
        builder.add_edge("leave_skill", "primary_assistant")

        builder.add_node(
            "enter_book_car_rental",
            create_entry_node("Car Rental Assistant", "book_car_rental"),
        )
        builder.add_node("book_car_rental", Assistant(book_car_rental_runnable))
        builder.add_edge("enter_book_car_rental", "book_car_rental")
        builder.add_node(
            "book_car_rental_safe_tools",
            create_tool_node_with_fallback(self.book_car_rental_safe_tools),
        )
        builder.add_node(
            "book_car_rental_sensitive_tools",
            create_tool_node_with_fallback(self.book_car_rental_sensitive_tools),
        )

        def route_book_car_rental(
            state: State,
        ):
            route = tools_condition(state)
            if route == END:
                return END
            tool_calls = state["messages"][-1].tool_calls
            did_cancel = any(
                tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls
            )
            if did_cancel:
                return "leave_skill"
            safe_toolnames = [t.name for t in self.book_car_rental_safe_tools]
            if all(tc["name"] in safe_toolnames for tc in tool_calls):
                return "book_car_rental_safe_tools"
            return "book_car_rental_sensitive_tools"

        builder.add_edge("book_car_rental_sensitive_tools", "book_car_rental")
        builder.add_edge("book_car_rental_safe_tools", "book_car_rental")
        builder.add_conditional_edges(
            "book_car_rental",
            route_book_car_rental,
            [
                "book_car_rental_safe_tools",
                "book_car_rental_sensitive_tools",
                "leave_skill",
                END,
            ],
        )

        # Hotel booking assistant
        builder.add_node(
            "enter_book_hotel",
            create_entry_node("Hotel Booking Assistant", "book_hotel"),
        )
        builder.add_node("book_hotel", Assistant(book_hotel_runnable))
        builder.add_edge("enter_book_hotel", "book_hotel")
        builder.add_node(
            "book_hotel_safe_tools",
            create_tool_node_with_fallback(self.book_hotel_safe_tools),
        )
        builder.add_node(
            "book_hotel_sensitive_tools",
            create_tool_node_with_fallback(self.book_hotel_sensitive_tools),
        )

        def route_book_hotel(
            state: State,
        ):
            route = tools_condition(state)
            if route == END:
                return END
            tool_calls = state["messages"][-1].tool_calls
            did_cancel = any(
                tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls
            )
            if did_cancel:
                return "leave_skill"
            tool_names = [t.name for t in self.book_hotel_safe_tools]
            if all(tc["name"] in tool_names for tc in tool_calls):
                return "book_hotel_safe_tools"
            return "book_hotel_sensitive_tools"

        builder.add_edge("book_hotel_sensitive_tools", "book_hotel")
        builder.add_edge("book_hotel_safe_tools", "book_hotel")
        builder.add_conditional_edges(
            "book_hotel",
            route_book_hotel,
            ["leave_skill", "book_hotel_safe_tools", "book_hotel_sensitive_tools", END],
        )

        # Excursion assistant
        builder.add_node(
            "enter_book_excursion",
            create_entry_node("Trip Recommendation Assistant", "book_excursion"),
        )
        builder.add_node("book_excursion", Assistant(book_excursion_runnable))
        builder.add_edge("enter_book_excursion", "book_excursion")
        builder.add_node(
            "book_excursion_safe_tools",
            create_tool_node_with_fallback(self.book_excursion_safe_tools),
        )
        builder.add_node(
            "book_excursion_sensitive_tools",
            create_tool_node_with_fallback(self.book_excursion_sensitive_tools),
        )

        def route_book_excursion(
            state: State,
        ):
            route = tools_condition(state)
            if route == END:
                return END
            tool_calls = state["messages"][-1].tool_calls
            did_cancel = any(
                tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls
            )
            if did_cancel:
                return "leave_skill"
            tool_names = [t.name for t in self.book_excursion_safe_tools]
            if all(tc["name"] in tool_names for tc in tool_calls):
                return "book_excursion_safe_tools"
            return "book_excursion_sensitive_tools"

        builder.add_edge("book_excursion_sensitive_tools", "book_excursion")
        builder.add_edge("book_excursion_safe_tools", "book_excursion")
        builder.add_conditional_edges(
            "book_excursion",
            route_book_excursion,
            [
                "book_excursion_safe_tools",
                "book_excursion_sensitive_tools",
                "leave_skill",
                END,
            ],
        )

        # Primary assistant
        builder.add_node("primary_assistant", Assistant(assistant_runnable))
        builder.add_node(
            "primary_assistant_tools",
            create_tool_node_with_fallback(self.primary_assistant_tools),
        )

        def route_primary_assistant(
            state: State,
        ):
            route = tools_condition(state)
            if route == END:
                return END
            tool_calls = state["messages"][-1].tool_calls
            if tool_calls:
                if tool_calls[0]["name"] == ToFlightBookingAssistant.__name__:
                    return "enter_update_flight"
                elif tool_calls[0]["name"] == ToBookCarRental.__name__:
                    return "enter_book_car_rental"
                elif tool_calls[0]["name"] == ToHotelBookingAssistant.__name__:
                    return "enter_book_hotel"
                elif tool_calls[0]["name"] == ToBookExcursion.__name__:
                    return "enter_book_excursion"
                return "primary_assistant_tools"
            raise ValueError("Invalid route")

        # The assistant can route to one of the delegated assistants,
        # directly use a tool, or directly respond to the user
        builder.add_conditional_edges(
            "primary_assistant",
            route_primary_assistant,
            [
                "enter_update_flight",
                "enter_book_car_rental",
                "enter_book_hotel",
                "enter_book_excursion",
                "primary_assistant_tools",
                END,
            ],
        )
        builder.add_edge("primary_assistant_tools", "primary_assistant")

        # Each delegated workflow can directly respond to the user
        # When the user responds, we want to return to the currently active workflow
        def route_to_workflow(
            state: State,
        ) -> Literal[
            "primary_assistant",
            "update_flight",
            "book_car_rental",
            "book_hotel",
            "book_excursion",
        ]:
            """If we are in a delegated state, route directly to the appropriate assistant."""
            dialog_state = state.get("dialog_state")
            if not dialog_state:
                return "primary_assistant"
            return dialog_state[-1]

        builder.add_conditional_edges("fetch_user_info", route_to_workflow)

        # 编译图形
        conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
        # conn.execute("DROP TABLE IF EXISTS checkpoints")
        memory = SqliteSaver(conn)
        part_4_graph = builder.compile(
            checkpointer=memory,
            interrupt_before=[
                "update_flight_sensitive_tools",
                "book_car_rental_sensitive_tools",
                "book_hotel_sensitive_tools",
                "book_excursion_sensitive_tools",
            ],
        )

        return part_4_graph


# # 初始化 GraphBuilder，只执行一次
# graph_builder = GraphBuilder(init_db=True)

# # 当需要创建图形时，调用 create_graph 方法，并传入新的 stream_handler
# def get_graph(stream_handler):
#     return graph_builder.create_graph(stream_handler)
