from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSerializable
from langchain_core.messages import SystemMessage

from app.agents.data_explorer.state import GraphState
from app.utils.helper import (
    invoke_runnable_with_usage_callback,
    compose_message_context
)
from app import config


SYSTEM_PROMPT = """
**결과 요약 (Summary)**:
- 당신은 필요한 지금까지의 수집된 데이터 분석 결과를 바탕으로 요약하여 `사용자의 원래 질문`에 응답합니다. 
- 사용자가 이해하기 쉬운 **핵심적인 내용을 요약**하여, 간결하고 명확한 문장으로 최종 보고서를 작성합니다.
- 사용자의 질문에 대한 대답을 할 수 있는 요약을 작성합니다. 예를 들어, "총 5개의 제품이 검색되었으며, 가장 인기 있는 제품은 'A'입니다." 와 같이 요약해 주세요.
- 만약 사용자 질문에 정확히 대답할 수 없다면, 정확한 정보를 확인할 수 없다고 알려주세요.
""".rstrip()

REASONING = False


def get_runnable_chain() -> RunnableSerializable:
    llm = config.get_default_llm(reasoning=REASONING)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "**사용자의 원래 질문**:\n{user_question}")
        ]
    )
    chain = prompt_template | llm
    return chain


def node(state: GraphState) -> dict:
    chain = get_runnable_chain()
    response = invoke_runnable_with_usage_callback(chain, state)
    response = compose_message_context(response)
    return {"messages": [response]}
