from components.tools.chatbots_tools.policy_lookup_tool import PolicyLookupTool
from components.tools.chatbots_tools.trip_recommendation_tool import TripRecommendationTool
from components.tools.chatbots_tools.database_updater_tool import DatabaseUpdaterTool
from components.tools.chatbots_tools.flight_service_tool import FlightServiceTool
from components.tools.chatbots_tools.hotel_service_tool import HotelServiceTool
from components.tools.chatbots_tools.car_rental_service_tool import CarRentalServiceTool
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode

db_tool = None

def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)

def init_and_get_tools(init_db=True):
    policy_tool = PolicyLookupTool()
    db_tool = DatabaseUpdaterTool()
    db = db_tool.update_dates(init_db=init_db)
    trip_tool = TripRecommendationTool(db)
    flight_tool = FlightServiceTool(db)
    hotel_tool = HotelServiceTool(db)
    car_rental_tool = CarRentalServiceTool(db)
    
    return policy_tool.lookup_policy, \
        trip_tool.search_trip_recommendations, \
        trip_tool.book_excursion, \
        trip_tool.update_excursion, \
        trip_tool.cancel_excursion, \
        flight_tool.fetch_user_flight_information, \
        flight_tool.search_flights, \
        flight_tool.update_ticket_to_new_flight, \
        flight_tool.cancel_ticket, \
        hotel_tool.search_hotels, \
        hotel_tool.book_hotel, \
        hotel_tool.update_hotel, \
        hotel_tool.cancel_hotel, \
        car_rental_tool.search_car_rentals, \
        car_rental_tool.book_car_rental, \
        car_rental_tool.update_car_rental, \
        car_rental_tool.cancel_car_rental

def update_dates():
    global db_tool
    if db_tool is None:
        db_tool = DatabaseUpdaterTool()
    return db_tool.update_dates()
