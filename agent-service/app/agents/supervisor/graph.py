from typing import Literal

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, MessagesState, START
from pydantic import BaseModel, Field

from app.agents import document_qa, code_assistant, data_explorer, casual_chat
from app import config


system_prompt = """
당신은 AI 에이전트 시스템의 지능형 라우팅 감독관입니다.

당신의 **유일한 임무**는 사용자의 최신 질문을 **내용이 아닌 유형에 따라** 분류하고, 가장 적합한 전문가에게 즉시 작업을 전달하는 것입니다.
**중요:** 이전까지의 대화 내용이나 주제에 대해 관여하지 마세요. 이전 내용과 관련이 없더라도 사용자가 현재 의도하는 바에 따라 적합한 전문가에게 작업을 분배하는 것이 최우선 사항입니다.

**행동 원칙**
- **신속한 분류**: 질문의 내용을 깊게 이해하거나 해결 방법을 생각하지 마세요. 오직 어느 카테고리에 속하는지만을 신속하게 판단합니다.
- **답변 금지**: 어떠한 경우에도 사용자의 질문에 직접 답변하지 않습니다.
- **단일 책임**: 당신의 책임은 오직 '라우팅'입니다.

**전문가 목록**
- `Document_QA`: 사내 문서, 정책, 매뉴얼 등 특정 사내 정보에 대한 질문.
- `Code_Assistant`: 코드 작성, 수정, 분석, 디버깅과 관련된 질문.
- `Data_Explorer`: 데이터 분석(EDA), 데이터베이스 조회, 통계 관련 질문일 경우
- `Casual_Chat`: 위 경우에 해당하지 않는 일반적인 대화, 인사, 상식 및 잡담.

주어진 전문가 목록 중 하나를 반드시 선택하여 `Route`도구의 `next`로 전달하세요.
""".rstrip()


class Route(BaseModel):
    """어떤 에이전트를 다음으로 호출할지 결정합니다."""
    next: Literal["Document_QA", "Code_Assistant", "Data_Explorer", "Casual_Chat"] = Field(..., description="다음 경로.")


def get_supervisor_chain():
    llm = config.get_default_llm(reasoning=True) # TODO: Consider about reasoning
    llm = llm.bind_tools(tools=[Route], tool_choice="Route")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(system_prompt),
            MessagesPlaceholder(variable_name="messages")
        ]
    )

    chain = prompt_template | llm
    return chain


class SupervisorState(MessagesState):
    next: str


def supervisor_node(state: SupervisorState):
    chain = get_supervisor_chain()
    # TODO: Consider trim_messages to ignore past interactions.
    messages = state['messages']
    response = chain.invoke({"messages": messages})
    if not response.tool_calls:
        # Supervisor가 라우팅 역할에 충실하지 않고 직접 답변을 한 경우, 한번의 추가 지침을 줍니다.
        response = chain.invoke({"messages": messages + [HumanMessage(content="Route 도구를 호출하세요.")]})
    route = response.tool_calls[0]['args']
    return {"next": route["next"]}


workflow = StateGraph(SupervisorState)

workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Document_QA", document_qa.graph)
workflow.add_node("Code_Assistant", code_assistant.graph)
workflow.add_node("Data_Explorer", data_explorer.graph)
workflow.add_node("Casual_Chat", casual_chat.graph)

workflow.add_edge(START, "Supervisor")
workflow.add_conditional_edges(
    "Supervisor",
    lambda state: state["next"],
    {
        "Document_QA": "Document_QA",
        "Code_Assistant": "Code_Assistant",
        "Data_Explorer": "Data_Explorer",
        "Casual_Chat": "Casual_Chat"
    }
)

graph = workflow.compile()
