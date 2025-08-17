from typing import Literal

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.agents.casual_chat.tools import all_tools
from app.utils.helper import (
    invoke_runnable_with_usage_callback,
    compose_message_context
)
from app import config


SYSTEM_PROMPT = """
당신은 `Jay`라는 이름의 대화형 AI입니다.

사용자의 질문에 답변하기 위해 다음 단계를 따르세요:
1. 먼저, 질문에 답하기 위해 사용 가능한 도구가 필요한지 생각합니다.
2. **만약 도구가 필요하다면**, 필요한 도구를 호출하세요.
3. **만약 도구가 필요 없다면**, 당신의 내부 지식을 사용하여 사용자의 질문에 직접 답변하세요.
""".rstrip()

REASONING = True


def get_casual_chat_chain():
    llm = config.get_default_llm(reasoning=REASONING)
    llm = llm.bind_tools(tools=all_tools)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages")
        ]
    )
    chain = prompt_template | llm
    return chain


def casual_chat_node(state: MessagesState):
    chain = get_casual_chat_chain()
    response = invoke_runnable_with_usage_callback(chain, state)
    response = compose_message_context(response)
    return {"messages": [response]}


def tools_condition(state: MessagesState) -> Literal["Casual_Chat.tools", "__end__"]:
    message = state['messages'][-1] 
    # When llm wants tool calling
    if hasattr(message, "tool_calls") and len(message.tool_calls) > 0:
        return "Casual_Chat.tools"
    # Otherwise
    return END


workflow = StateGraph(state_schema=MessagesState)

workflow.add_node("Casual_Chat", casual_chat_node)
workflow.add_node("Casual_Chat.tools", ToolNode(all_tools))

workflow.add_edge(START, "Casual_Chat")
workflow.add_conditional_edges("Casual_Chat", tools_condition)
workflow.add_edge("Casual_Chat.tools", "Casual_Chat")
workflow.add_edge("Casual_Chat", END)

graph = workflow.compile()
