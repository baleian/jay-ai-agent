"""
TODO: 
- loop(loop(스키마 조회 -> 쿼리 플래닝) -> 플랜 검증) -> 쿼리 생성 -> 실행 -> 요약 등으로 변경 가능
- 여러 소스의 데이터를 각각 조회하고 요약해야 하는 경우 JOIN으로 불가능 하므로, `쿼리 생성` 단계에서 하나의 쿼리가 아닌 복수 쿼리와 데이터 소스가 생성될 수 있음을 고려
"""

from typing import Literal

from langgraph.graph import StateGraph, START, END

from app.agents.data_explorer.state import GraphState
from app.agents.data_explorer.nodes import text_to_sql, sql_corrector, sql_executor, summary


def text_to_sql_tools_condition(state: GraphState) -> Literal["Text_to_SQL.tools", "SQL_Corrector", "__end__"]:
    # When llm generated output
    if "generated_sql" in state:
        return "SQL_Corrector"
    
    # When llm wants tool calling
    response = state["messages"][-1]
    if hasattr(response, "tool_calls") and len(response.tool_calls) > 0:
        return "Text_to_SQL.tools"
    
    # Otherwise
    return END
    

def sql_corrector_tools_condition(state: GraphState) -> Literal["SQL_Corrector.tools", "SQL_Executor", "__end__"]:
    # When llm generated output
    if "corrected_sql" in state:
        return "SQL_Executor"
    
    # When llm wants tool calling
    response = state["messages"][-1]
    if hasattr(response, "tool_calls") and len(response.tool_calls) > 0:
        return "SQL_Corrector.tools"
    
    # Otherwise
    return END


def sql_executor_tools_condition(state: GraphState) -> Literal["SQL_Executor.tools", "__end__"]:
    response = state["messages"][-1]
    # When llm wants tool calling
    if hasattr(response, "tool_calls") and len(response.tool_calls) > 0:
        return "SQL_Executor.tools"
    
    # Otherwise
    return END
    

workflow = StateGraph(GraphState)

workflow.add_node("Text_to_SQL", text_to_sql.node)
workflow.add_node("Text_to_SQL.tools", text_to_sql.tool_nodes)
workflow.add_node("SQL_Corrector", sql_corrector.node)
workflow.add_node("SQL_Corrector.tools", sql_corrector.tool_nodes)
workflow.add_node("SQL_Executor", sql_executor.node)
workflow.add_node("SQL_Executor.tools", sql_executor.tool_nodes)
workflow.add_node("Summary", summary.node)

workflow.add_edge(START, "Text_to_SQL")
workflow.add_conditional_edges("Text_to_SQL", text_to_sql_tools_condition)
workflow.add_edge("Text_to_SQL.tools", "Text_to_SQL")
workflow.add_conditional_edges("SQL_Corrector", sql_corrector_tools_condition)
workflow.add_edge("SQL_Corrector.tools", "SQL_Corrector")
workflow.add_conditional_edges("SQL_Executor", sql_executor_tools_condition)
workflow.add_edge("SQL_Executor.tools", "Summary")
workflow.add_edge("Summary", END)

graph = workflow.compile()
