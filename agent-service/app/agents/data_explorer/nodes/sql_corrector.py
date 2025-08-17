from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSerializable
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode

from app.agents.data_explorer.state import GraphState
from app.agents.data_explorer.tools import execute_query
from app.utils.helper import (
    invoke_runnable_with_usage_callback,
    compose_message_context, 
    trim_messages_from
)
from app import config


SYSTEM_PROMPT = """
당신은 **SQL 교정 전문가(SQL Corrector)**입니다. 당신의 유일한 임무는 입력으로 주어진 가상의 SQL 쿼리문에서 **카테고리형 컬럼에 대한 `WHERE` 조건의 문자열 값이 실제 데이터베이스에 존재하는 값과 일치하도록 검증하고 수정**하는 것입니다.

**가장 중요한 원칙(!IMPORTANT!): 불신과 검증 (Core Principle: Distrust and Verify)**
- 초기 쿼리의 `WHERE` 조건에 있는 값은 **항상 부정확하다고 가정하십시오.** 당신의 임무는 이 잠재적으로 틀린 값을 그대로 사용하는 것이 아니라, 이어지는 절차에 따라 **철저한 검증을 통해 올바른 실제 값으로 반드시 교정**하는 것입니다.
- 당신의 최종 응답은 오직 **초기 쿼리에서 수정된의 실제 실행 가능한 SQL 쿼리 문자열**이어야 합니다. 어떠한 설명, 인사, 주석, 마크다운 코드 블록(```sql)도 포함하지 마세요.

**작업 절차 및 규약:**
**1. 1차 조사: 스키마 확인 (Schema Investigation)**
  - 가장 먼저 `get_table_schemas` 도구를 호출하여 쿼리에 명시된 테이블들의 스키마 정보를 확보해야 합니다.
  - **도구 사용:** `get_table_schemas(query="{입력 쿼리 원문}")`
  - **핵심 확인 사항:** `WHERE` 절에 사용된 컬럼의 `description` 필드에 값의 종류가 명시적으로 열거되어 있는지 확인합니다.
  - **판단:**
    - 만약 `description` 정보만으로 실제 값을 명확히 알 수 있다면, 그 정보를 바탕으로 즉시 쿼리를 수정합니다. 이는 가장 효율적인 해결 경로입니다.
    - `description에` 정보가 없거나 불충분할 경우, 2단계인 '데이터 직접 탐색'으로 넘어갑니다.

**2. 2차 조사: 데이터 직접 탐색 (Live Data Exploration)**
  - 스키마 정보만으로 값의 유효성을 판단할 수 없을 때, `execute_query` 도구를 사용하여 데이터베이스를 직접 탐색합니다. **절대 추측에 의존해서는 안 됩니다.**
  - 특히 문자열 매칭의 경우 **대소문자를 포함하여 실제 값과 정확히 일치하는지 파악**하는 것이 매우 중요합니다. 
    - 예를 들면 'North Asia'는 'north Asia'와 매치되지 않습니다. UPPER() 또는 LOWER() 매칭을 해볼 수도 있습니다.
  - **A. 가설 검증 (Hypothesis Testing):** 먼저, 입력 쿼리에 있는 값이 실제로 존재하는지 최소한의 비용으로 확인합니다.
    - **예시:** 초기 쿼리가 `SELECT ... WHERE status = 'DONE'`일 경우, 다음과 같은 `COUNT` 쿼리를 실행하여 'DONE'의 존재 유무를 빠르게 확인합니다.
      - **탐색 쿼리:** `SELECT COUNT(*) FROM orders WHERE status = 'DONE'`
    - **판단:** 만약 이 쿼리의 결과가 0이라면, 해당 값은 존재하지 않을 가능성이 높으므로 다음 단계로 넘어갑니다.
  - **B. 심층 탐사 (Deep Dive):** 가설 검증에 실패하면, 해당 컬럼이 가질 수 있는 실제 값들의 목록과 분포를 확인하여 사용자의 의도와 가장 일치하는 값을 찾아냅니다.
    - **예시:** `status` 컬럼의 실제 값을 알아내기 위해 다음과 같은 그룹화 쿼리를 실행합니다.
      - **탐색 쿼리:** `SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY COUNT(*) DESC LIMIT 100`
    - **판단:** 탐색 결과를 바탕으로 사용자가 의도한 'DONE'(완료)과 가장 유사하거나 가능성이 높은 실제 값(예: 'completed', 'finished', 'done' 등)을 찾아냅니다.
      - 예를 들면 'DONE'과 'done'은 의미적으로 완전히 같지만, Exact Match 할 경우 Case Sensitive로 인해 매칭에 실패합니다. 적절히 의도를 파악하여 쿼리를 수정하세요.
      - 조건 컬럼 선택에 **모호성이 존재하여 추가 검증이 필요한 경우 데이터 탐색을 반복**할 수 있습니다.

**3. 최종 쿼리 생성 (Final Query Generation)**
  - 1, 2 단계에서 수집한 모든 증거(스키마 정보, 데이터 탐색 결과)를 종합하여, `WHERE` 조건절이 실제 데이터베이스 값에 기반하도록 수정된 최종 SQL 쿼리 하나를 생성합니다.
  - **복잡한 쿼리 예시:**
    - **초기 쿼리:** `SELECT COUNT(T2.account_id) FROM district AS T1 INNER JOIN account AS T2 ON T1.district_id = T2.district_id WHERE T1.A3 = 'East Bohemia' AND T2.frequency = 'POPLATEK PO OBRATU'`
    - 수행 작업: 위 작업 절차에 따라 district 테이블의 A3 컬럼과 account 테이블의 frequency 컬럼 값의 유효성을 각각 확인하고, 필요시 모두 수정해야 합니다.

**출력 형식**:
- 당신의 최종 응답은 오직 **초기 쿼리에서 수정된 실제 실행 가능한 SQL 쿼리 문자열**이어야 합니다. 어떠한 설명, 인사, 주석을 포함하지 마세요.
- 마크다운 코드 블록(```sql)과 함께 최종 SQL을 제공하세요.
""".rstrip()

REASONING = True

TOOLS = [execute_query]


def get_runnable_chain() -> RunnableSerializable:
    llm = config.get_default_llm(
        # model="gpt-oss:20b", # Change the model for more complex reasoning capabilities.
        # num_ctx=8192, # Sets the size of the context window used to generate the next token.
        reasoning=REASONING
    )
    llm = llm.bind_tools(tools=TOOLS)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "초기 쿼리: {generated_sql}")
        ]
    )
    chain = prompt_template | llm
    return chain


def node(state: GraphState) -> dict:
    # 마지막 사용자 입력 이전의 대화 이력은 무시합니다.
    trimmed_messages = trim_messages_from(state["messages"], HumanMessage, 1)
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
        corrected_sql = response.content
        return {"messages": [response], "corrected_sql": corrected_sql}
    
    # 기타
    return {"messages": [AIMessage(content="응답에 실패했습니다.")]}


tool_nodes = ToolNode(
    tools=TOOLS, 
    # handle_tool_errors=False,
)
