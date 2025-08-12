import json
from typing import Literal, List

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.agents.data_explorer.tools import (
    get_table_schemas,
    execute_query
)
from app.utils.helper import compose_message_context
from app import config


text_to_sql_tools = [get_table_schemas]
sql_corrector_tools = [execute_query]
sql_executor_tools = [execute_query]


def get_text_to_sql_chain():
    llm = config.get_default_llm()
    llm.reasoning = True
    llm = llm.bind_tools(tools=text_to_sql_tools)

    system_prompt = """
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

    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(system_prompt),
            MessagesPlaceholder(variable_name="messages")
        ]
    )

    chain = prompt_template | llm
    return chain


def get_sql_corrector_chain():
    llm = config.get_default_llm()
    # llm.model = "gpt-oss:20b" # Change the model for more complex reasoning capabilities.
    # llm.num_ctx = 8192 # Sets the size of the context window used to generate the next token.
    llm.reasoning = True
    llm = llm.bind_tools(tools=sql_corrector_tools)

    system_prompt = """
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

    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "초기 쿼리: {generated_sql}")

        ]
    )

    chain = prompt_template | llm
    return chain


def get_sql_executor_chain():
    llm = config.get_default_llm()
    llm = llm.bind_tools(tools=sql_executor_tools)

    system_prompt = """
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

    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(system_prompt),
            ("human", "{generated_sql}")
        ]
    )

    chain = prompt_template | llm
    return chain


def get_summary_chain():
    llm = config.get_default_llm()

    system_prompt = """
- 당신은 `Query Result`의 데이터를 분석합니다. 
- 사용자가 이해하기 쉬운 **핵심적인 내용을 요약**하여, 간결하고 명확한 문장으로 최종 보고서를 작성합니다.
- 사용자의 질문에 대한 대답을 할 수 있는 요약을 작성합니다. 예를 들어, "총 5개의 제품이 검색되었으며, 가장 인기 있는 제품은 'A'입니다." 와 같이 요약해 주세요.
- 만약 사용자 질문에 정확히 대답할 수 없다면, 정확한 정보를 확인할 수 없다고 알려주세요.
""".rstrip()
    
    prompt = """
`User Question`: {user_question}

`Generated SQL`: {generated_sql}

`Query Result`: {query_result}
""".rstrip()

    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            ("human", prompt)
        ]
    )

    chain = prompt_template | llm
    return chain


class DataExplorerState(MessagesState):
    user_question: str
    generated_sql: str
    query_result: List[dict]


def text_to_sql_node(state: DataExplorerState):
    chain = get_text_to_sql_chain()
    response = chain.invoke(state)
    response = compose_message_context(response)
    update_state = {"messages": [response]}

    # 마지막 input message가 사람이인 경우
    if isinstance(state["messages"][-1], HumanMessage):
        update_state["user_question"] = state["messages"][-1].content

    # Text to SQL 노드의 응답 결과가 있는 경우 (Tool calling 제외)
    if response.content:
        update_state["generated_sql"] = response.content
    return update_state


def sql_corrector_node(state: DataExplorerState):
    chain = get_sql_corrector_chain()

    # 직전 사용자 입력 이전의 대화 이력은 무시합니다.
    if isinstance(state["messages"][-1], HumanMessage):
        messages = [state["messages"][-1]]
    # Agent loop 하면서 생성한 context는 모두 활용합니다.
    else:
        messages = state["messages"]
    
    response = chain.invoke({"messages": messages, "generated_sql": state["generated_sql"]})
    response = compose_message_context(response)
    update_state = {"messages": [response]}

    # Text to SQL 노드의 응답 결과가 있는 경우 (Tool calling 제외)
    if response.content:
        update_state["generated_sql"] = response.content
    return update_state


def sql_executor_node(state: DataExplorerState):
    # execute_query 도구 호출 결과가 정상적인 경우, 그래프 상태 업데이트 후 종료
    # TODO: 도구 이름 확인, 메시지 구조화 등 리팩토링 필요
    if isinstance(state["messages"][-1], ToolMessage):
        query_result = json.loads(state["messages"][-1].content)
        if isinstance(query_result, dict) and "data" in query_result:
            return {"query_result": query_result.get("data", [])}
    
    chain = get_sql_executor_chain()
    response = chain.invoke(state)
    response = compose_message_context(response)
    return {"messages": [response]}


def summary_node(state: DataExplorerState):
    chain = get_summary_chain()
    response = chain.invoke(state)
    response = compose_message_context(response)
    return {"messages": [response]}


def text_to_sql_tools_condition(state: DataExplorerState) -> Literal["Text_to_SQL.tools", "SQL_Corrector", "__end__"]:
    response = state["messages"][-1]
    # When llm wants tool calling
    if hasattr(response, "tool_calls") and len(response.tool_calls) > 0:
        return "Text_to_SQL.tools"
    # When llm generated some content
    elif "generated_sql" in state:
        return "SQL_Corrector"
    # Otherwise
    else:
        return END
    

def sql_corrector_tools_condition(state: DataExplorerState) -> Literal["SQL_Corrector.tools", "SQL_Executor"]:
    response = state["messages"][-1]
    # When llm wants tool calling
    if hasattr(response, "tool_calls") and len(response.tool_calls) > 0:
        return "SQL_Corrector.tools"
    # Otherwise then to next node
    else:
        return "SQL_Executor"
    

def sql_executor_tools_condition(state: DataExplorerState) -> Literal["SQL_Executor.tools", "Summary", "__end__"]:
    response = state["messages"][-1]
    # When llm wants tool calling
    if hasattr(response, "tool_calls") and len(response.tool_calls) > 0:
        return "SQL_Executor.tools"
    # When llm executed query and got result
    elif "query_result" in state:
        return "Summary"
    # Otherwise
    else:
        return END
    

workflow = StateGraph(DataExplorerState)

workflow.add_node("Text_to_SQL", text_to_sql_node)
workflow.add_node("Text_to_SQL.tools", ToolNode(text_to_sql_tools))
workflow.add_node("SQL_Corrector", sql_corrector_node)
workflow.add_node("SQL_Corrector.tools", ToolNode(sql_corrector_tools))
workflow.add_node("SQL_Executor", sql_executor_node)
workflow.add_node("SQL_Executor.tools", ToolNode(sql_executor_tools))
workflow.add_node("Summary", summary_node)

workflow.add_edge(START, "Text_to_SQL")
workflow.add_conditional_edges("Text_to_SQL", text_to_sql_tools_condition)
workflow.add_edge("Text_to_SQL.tools", "Text_to_SQL")
workflow.add_conditional_edges("SQL_Corrector", sql_corrector_tools_condition)
workflow.add_edge("SQL_Corrector.tools", "SQL_Corrector")
workflow.add_conditional_edges("SQL_Executor", sql_executor_tools_condition)
workflow.add_edge("SQL_Executor.tools", "SQL_Executor")
workflow.add_edge("Summary", END)

graph = workflow.compile()
