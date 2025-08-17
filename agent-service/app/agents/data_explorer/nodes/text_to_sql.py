from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSerializable
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode

from app.agents.data_explorer.state import GraphState
from app.agents.data_explorer.tools import get_table_schemas
from app.utils.helper import (
    invoke_runnable_with_usage_callback,
    compose_message_context, 
    trim_messages_from
)
from app import config


SYSTEM_PROMPT = """
당신은 전문가 수준의 Text-to-SQL 에이전트입니다. 당신의 유일한 임무는 사용자의 자연어 질문을 정확하고 실행 가능한 SQL 쿼리로 변환하는 것입니다.

**당신의 작업 절차**:
1. **스키마 발견 (가장 중요한 첫 단계)**: 사용자의 질문을 분석한 후, 반드시 `get_table_schemas` 도구를 먼저 호출하여 질문과 관련된 테이블 스키마 정보를 얻어야 합니다. 절대 테이블이나 컬럼 이름을 스스로 추측해서는 안 됩니다.
2. **스키마 기반 SQL 생성**: `get_table_schemas` 도구를 통해 얻은 테이블 이름, 컬럼명, 데이터 타입 등 실제 스키마 정보를 바탕으로 SQL 쿼리를 작성합니다.
3. **정확한 쿼리 작성**: 사용자의 의도를 정확히 반영하는 SQL을 생성하세요. 올바른 JOIN, WHERE 절, 집계 함수를 사용해야 합니다.
  - 사용자의 질문에 문자열 기반의 조건절(`WHERE`)이 포함되어 있습니까?
  - 그렇다면, 사용자가 질문에서 언급한 값을 `WHERE` 절에 직접 사용해야 합니다. 어떤 값이 있는지 **스스로 추측하지 마세요**.
4. **SQLite 문법 준수**: 생성된 모든 SQL 쿼리는 SQLite 데이터베이스에서 실행 가능해야 합니다. 표준 SQL을 우선적으로 사용하되, 날짜/시간 함수(`strftime` 등)와 같이 SQLite의 특정 구문을 따라야 할 경우 이를 반드시 준수하세요.

**출력 형식**:
- 당신의 최종 응답은 오직 **순수한 SQL 쿼리 문자열**이어야 합니다. 어떠한 설명, 인사, 주석도 포함하지 마세요.
- 마크다운 코드 블록(```sql)과 함께 최종 SQL을 제공하세요.
""".rstrip()

REASONING = True

TOOLS = [get_table_schemas]


def get_runnable_chain() -> RunnableSerializable:
    llm = config.get_default_llm(reasoning=REASONING)
    llm = llm.bind_tools(tools=TOOLS)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages")
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
    response = invoke_runnable_with_usage_callback(chain, state)
    response = compose_message_context(response)

    # Tool 호출의 경우
    if response.tool_calls:
        return {"messages": [response]}
    
    # LLM 응답이 있는 경우
    if response.content:
        # 마지막으로 유저가 입력한 유저의 질문
        user_question = trim_messages_from(state["messages"], HumanMessage, 1)[0]
        generated_sql = response.content
        return {"messages": [response], "user_question": user_question, "generated_sql": generated_sql}
    
    # 기타
    return {"messages": [AIMessage(content="응답에 실패했습니다.")]}


tool_nodes = ToolNode(
    tools=TOOLS, 
    # handle_tool_errors=False,
)