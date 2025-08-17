from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState, add_messages


class GraphState(MessagesState):
    user_question: str
    generated_sql: str
    corrected_sql: str
