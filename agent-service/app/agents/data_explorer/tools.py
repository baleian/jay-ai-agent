from typing import List
import requests

from langchain_core.tools import tool

from app.utils import rag
from app import config


# TODO: Response schema를 pydantic 같은 걸로 구체화하여 퍼포먼스 비교
@tool
def get_table_schemas(query: str) -> List[dict]:
    """
    유저가 원하는 데이터를 조회하기 위해 필요한 연관성이 높은 테이블 스키마를 검색할 때 사용합니다.
    Join과 같은 복잡한 SQL이 요구되는 경우, 관련 테이블이 여러개 있을 수 있습니다.
    Parameters:
    - query: VectorStore에서 검색하기 위한 쿼리. 자연어 기반으로 검색할 수 있으므로, 핵심 사용자 질문에 해당하는 자연어을 그대로 사용하세요.
    """
    collection_id = rag.get_collection_id_by_name(config.DB_TABLE_SCHEMAS_RAG_COLLECTION_NAME)
    return rag.document_search(collection_id, query, 10)


# TODO: Response schema를 pydantic 같은 걸로 구체화하여 퍼포먼스 비교
@tool
def execute_query(sql: str) -> dict:
    """
    SQLite 데이터베이스에 SQL을 실행하고 쿼리 결과를 응답합니다.
    Parameters:
    - sql: SQLite에서 실행 가능한 SQL 문자열
    """
    url = config.DW_SERVICE_URL + "/query"
    headers = {"Content-Type": "application/json"}
    payload = {"query": sql}
    response = requests.post(url, headers=headers, json=payload)
    return response.json()


all_tools = [
    get_table_schemas,
    execute_query
]
