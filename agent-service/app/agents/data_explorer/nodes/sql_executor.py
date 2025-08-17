from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSerializable
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode

from app.agents.data_explorer.state import GraphState
from app.agents.data_explorer.tools import execute_query
from app.utils.helper import (
    compose_message_context, 
    trim_messages_from,
    human_in_the_loop
)
from app import config


SYSTEM_PROMPT = """
당신은 'Secure Query Executor'라는 이름의 데이터베이스 인터페이스 에이전트입니다. 당신의 최우선 순위는 **데이터베이스의 안정성을 보장**하는 것이며, 오직 안전하다고 검증된 **읽기 전용(read-only)** 쿼리만을 실행합니다.

**쿼리 처리 프로토콜 (반드시 순서대로 따를 것)**:
1. **위험 평가 (Risk Assessment)**:
  - 입력된 쿼리가 읽기 전용 (`SELECT`) 쿼리 인지 확인합니다.
  - `UPDATE`, `DELETE`, `INSERT`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE` 등 데이터 수정/삭제 관련 키워드가 포함되어 있는지 확인합니다.
  - 만약 하나라도 금지된 키워드가 발견되면, 다른 모든 단계를 즉시 건너뛰고 **"데이터 조회를 위한 SELECT 쿼리만 실행 가능합니다."** 라는 메시지를 반환하세요.

2. **유효성 검증 (Validation)**:
  - 보안 검사를 통과한 쿼리가 SQLite 문법 표준을 준수하는지 확인합니다. 문법 오류가 예상되면, **"입력된 SQL의 문법이 올바르지 않습니다."** 라고 응답하세요.

3. **실행 위임 (Execution Delegation)**:
  - 모든 검증을 통과한 쿼리는 `execute_query` **도구를 사용**하여 데이터베이스로 전달합니다. 당신이 직접 쿼리를 실행하는 것이 아니라, 도구에 위임하는 역할입니다.

4. **결과 요약 (Summary)**:
  - 당신은 필요한 `대상 쿼리`를 모두 수행하여 **데이터를 수집 후** 지금까지의 데이터 분석 결과를 바탕으로 요약하여 `사용자의 원래 질문`에 응답합니다. 
  - 사용자가 이해하기 쉬운 **핵심적인 내용을 요약**하여, 간결하고 명확한 문장으로 최종 보고서를 작성합니다.
  - 사용자의 질문에 대한 대답을 할 수 있는 요약을 작성합니다. 예를 들어, "총 5개의 제품이 검색되었으며, 가장 인기 있는 제품은 'A'입니다." 와 같이 요약해 주세요.
  - 만약 사용자 질문에 정확히 대답할 수 없다면, 정확한 정보를 확인할 수 없다고 알려주세요.
""".rstrip()

USER_PROMPT = """
**사용자의 원래 질문**:
{user_question}

**대상 쿼리**:
{corrected_sql}
"""

REASONING = True

TOOLS = [execute_query]


def get_runnable_chain() -> RunnableSerializable:
    llm = config.get_default_llm(reasoning=REASONING)
    llm = llm.bind_tools(tools=TOOLS)
    
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            ("human", USER_PROMPT)
        ]
    )
    chain = prompt_template | llm
    return chain


def node(state: GraphState) -> dict:
    # 3번째 전 사용자 입력 이후의 대화 내용만 참고하여 결과를 생성합니다.
    trimmed_messages = trim_messages_from(state["messages"], HumanMessage, 3)
    # Node는 순수 함수여서 state 객체 업데이트는 그래프 영구 상태에는 영향을 주지 않으므로 안전합니다.
    state.update({"messages": trimmed_messages})
    
    chain = get_runnable_chain()
    response = chain.invoke(state)
    response = compose_message_context(response)
    
    # Tool 호출의 경우
    if response.tool_calls:
        # 쿼리 실행을 위한 사용자 승인 요청
        tool_calls = human_in_the_loop(response.tool_calls, allow_edit=True)
        if not tool_calls:
            return {"messages": [response, AIMessage(content="사용자가 요청을 취소했습니다.")]}
        response.tool_calls = tool_calls
        return {"messages": [response]}
    
    # LLM 응답이 있는 경우
    if response.content:
        return {"messages": [response]}
    
    # 기타
    return {"messages": [AIMessage(content="응답에 실패했습니다.")]}


tool_nodes = ToolNode(
    tools=TOOLS, 
    # handle_tool_errors=False,
)
