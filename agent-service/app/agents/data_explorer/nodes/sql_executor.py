from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSerializable
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode

from app.agents.data_explorer.state import GraphState
from app.agents.data_explorer.tools import execute_query
from app.utils.helper import (
    invoke_runnable_with_usage_callback,
    compose_message_context
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
""".rstrip()

REASONING = False

TOOLS = [execute_query]


def get_runnable_chain() -> RunnableSerializable:
    llm = config.get_default_llm(reasoning=REASONING)
    llm = llm.bind_tools(tools=TOOLS)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(SYSTEM_PROMPT),
            ("human", "**입력 쿼리**:\n{corrected_sql}")
        ]
    )
    chain = prompt_template | llm
    return chain


def node(state: GraphState) -> dict:
    chain = get_runnable_chain()
    response = invoke_runnable_with_usage_callback(chain, state)
    response = compose_message_context(response)
    
    # 도구 호출 성공
    if response.tool_calls:
        # # 쿼리 실행을 위한 사용자 승인 요청
        # tool_calls = human_in_the_loop(response.tool_calls, allow_edit=True)
        # if not tool_calls:
        #     return {"messages": [response, AIMessage(content="사용자가 요청을 취소했습니다.")]}
        # response.tool_calls = tool_calls
        return {"messages": [response]}

    return {"messages": [response]}


tool_nodes = ToolNode(
    tools=TOOLS, 
    # handle_tool_errors=False,
)
