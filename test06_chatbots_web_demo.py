import streamlit as st
from langchain.schema import ChatMessage
from archive.test06_chatbots import GraphBuilder
from langchain_core.messages import ToolMessage
from langchain.callbacks.base import BaseCallbackHandler
import uuid

st.title("ChatGPT-like Clone")

# 初始化配置
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

config = {
    "configurable": {
        "passenger_id": "3442 587242",
        "thread_id": st.session_state.thread_id,
    }
}

class StreamHandler(BaseCallbackHandler):
    def __init__(self, container, initial_text=""):
        self.container = container
        self.text = initial_text
        self.tool_container = st.container()
        self.tool_usages = []

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        # print("新的 token：", token)
        self.text += token
        self.container.markdown(self.text)
        
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "printed_ids" not in st.session_state:
    st.session_state.printed_ids = set()

if "awaiting_user_input" not in st.session_state:
    st.session_state.awaiting_user_input = False

if "tool_call" not in st.session_state:
    st.session_state.tool_call = None

if "partial_response" not in st.session_state:
    st.session_state.partial_response = ""

# 初始化 graph，仅在第一次加载时
if "graph_builder" not in st.session_state:
    with st.spinner("正在初始化图模型，这可能需要一些时间..."):
        st.session_state.graph_builder = GraphBuilder(init_db=True)
    st.success("图模型已成功加载！")  # 初始化完成提示

# 创建消息容器占位符
message_container = st.empty()

# 定义显示消息的函数
def display_messages():
    with message_container.container():
        for message in st.session_state.messages:
            with st.chat_message(message.role):
                st.markdown(message.content)

# # 显示历史消息
# for message in st.session_state.messages:
#     with st.chat_message(message.role):
#         st.markdown(message.content)
# 显示历史消息
display_messages()

# 用户输入处理
if prompt := st.chat_input("What is up?"):
    # 追加用户消息到会话状态
    st.session_state.messages.append(ChatMessage(role="user", content=prompt))

    # 显示用户消息
    with st.chat_message("user"):
        print(f"prompt: [{prompt}]")
        st.markdown(prompt)

    # 准备请求
    req = {"messages": [("user", prompt)]}

    # 处理事件
    with st.chat_message("assistant"):
        assistant_response = ""
        stream_handler = StreamHandler(st.empty())
        graph = st.session_state.graph_builder.create_graph(stream_handler)
        st.session_state.graph = graph  # 保存 graph 到 session_state

        events = graph.stream(req, config, stream_mode="values")

        for event in events:
            # 处理消息
            message = event.get("messages")
            if message:
                if isinstance(message, list):
                    message = message[-1]
                if message.id not in st.session_state.printed_ids:
                    if hasattr(message, "content"):
                        full_response = message.content
                    st.session_state.printed_ids.add(message.id)
                    if getattr(message, "tool_calls", None):
                        tool_call = message.tool_calls[0]
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        # 显示工具使用过程
                        with st.container():
                            sub_assistant_response = f"\n**助手正在请求使用工具：** `{tool_name}`\n**参数：** `{tool_args}`\n\n"
                            stream_handler.on_llm_new_token(sub_assistant_response)
                            assistant_response += sub_assistant_response

        # 检查是否需要用户输入
        snapshot = graph.get_state(config)
        if snapshot.next:
            st.session_state.awaiting_user_input = True
            st.session_state.tool_call = message.tool_calls[0]
            st.session_state.partial_response = full_response + assistant_response

        # 如果不需要用户输入，保存助手的回复
        if not st.session_state.awaiting_user_input:
            full_response = assistant_response + full_response
            print(f"full_response: [{full_response}]")
            st.session_state.messages.append(ChatMessage(role="assistant", content=full_response))

# 创建占位符
tool_request_container = st.empty()
approval_container = st.empty()
feedback_container = st.empty()

# 处理助手等待用户输入的情况
if st.session_state.get("awaiting_user_input", False):
    with tool_request_container.container():
        st.write("助手想要使用以下工具：")
        st.json(st.session_state.tool_call)

    # 提供用户批准或拒绝的选项
    with approval_container.container():
        user_input = st.radio(
            "您是否批准上述操作？",
            ("是", "否"),
            index=0,
            key="tool_approval"
        )

        if user_input == "是":
            continue_clicked = st.button("继续", key="continue_button")
            if continue_clicked:
                display_messages()
                graph = st.session_state.graph_builder.create_graph()

                # 继续处理
                result = graph.invoke(
                    None,
                    config
                )

                full_response = st.session_state.partial_response + result["messages"][-1].content
                st.session_state.messages.append(ChatMessage(role="assistant", content=full_response))
                st.session_state.awaiting_user_input = False
                # 清空占位符
                tool_request_container.empty()
                approval_container.empty()
                display_messages()

                # # 处理后续事件
                # with st.chat_message("assistant"):
                #     full_response = st.session_state.partial_response
                #     st.markdown(f"助手正在处理... {full_response}")
                #     events = graph.stream(None, config, stream_mode="values")
                #     st.markdown("正在继续处理...")
                #     for event in events:
                #         st.markdown("event 处理中...")
                #         # 处理消息
                #         message = event.get("messages")
                #         if message:
                #             if isinstance(message, list):
                #                 message = message[-1]
                #             if message.id not in st.session_state.printed_ids:
                #                 if hasattr(message, "content"):
                #                     full_response = st.session_state.partial_response + message.content
                #                 st.session_state.printed_ids.add(message.id)

                #     st.markdown("处理完成！")

                #     # 保存助手的回复
                #     st.session_state.messages.append(ChatMessage(role="assistant", content=full_response))
                #     st.session_state.awaiting_user_input = False
        else:
            with feedback_container.container():
                feedback = st.text_input(
                    "请提供您的反馈或请求的更改：",
                    key="user_feedback"
                )
                if st.button("提交反馈"):
                    graph = st.session_state.graph_builder.create_graph()
                    # 传递用户反馈
                    result = graph.invoke(
                        {
                            "messages": [
                                ToolMessage(
                                    tool_call_id=st.session_state.tool_call["id"],
                                    content=f"用户拒绝了 API 调用。原因：'{feedback}'。请根据用户的输入继续提供帮助。",
                                )
                            ]
                        },
                        config,
                    )

                    full_response = st.session_state.partial_response + result["messages"][-1].content
                    st.session_state.messages.append(ChatMessage(role="assistant", content=full_response))
                    st.session_state.awaiting_user_input = False
                    # 清空占位符
                    tool_request_container.empty()
                    approval_container.empty()
                    feedback_container.empty()
                    display_messages()

                    # # 处理后续事件
                    # with st.chat_message("assistant"):
                    #     full_response = st.session_state.partial_response

                    #     events = graph.stream(None, config, stream_mode="values")
                    #     for event in events:
                    #         # 处理消息
                    #         message = event.get("messages")
                    #         if message:
                    #             if isinstance(message, list):
                    #                 message = message[-1]
                    #             if message.id not in st.session_state.printed_ids:
                    #                 if hasattr(message, "content"):
                    #                     full_response = message.content + st.session_state.partial_response
                    #                 st.session_state.printed_ids.add(message.id)

                    #     # 保存助手的回复
                    #     st.session_state.messages.append(ChatMessage(role="assistant", content=full_response))
                    #     st.session_state.awaiting_user_input = False
