from typing import List

from langchain_core.tools import tool

from app.utils import rag
from app import config


# TODO: Response schema를 pydantic 같은 걸로 구체화하여 퍼포먼스 비교
@tool
def get_internal_documents(query: str, count: int = 4) -> List[dict]:
    """
    유저의 질의에 가장 연관성이 높은 문서를 검색할 때 사용합니다.
    일반적인 질문이 아닌 사내 문서 데이터베이스에서 조회가 필요할 때 연관 문서를 가져올 수 있습니다.
    Parameters:
    - query: VectorStore에서 검색하기 위한 쿼리.
    - count: 연관 문서 상위 몇개를 가져올 지. 기본값: 4
    """
    collection_id = rag.get_collection_id_by_name(config.INTERNAL_DOCUMENTS_RAG_COLLECTION_NAME)
    return rag.document_search(collection_id, query, count)


all_tools = [
    get_internal_documents
]
