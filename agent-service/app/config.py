from starlette.config import Config
from langchain_ollama import ChatOllama


env = Config()


LLM_SERVICE_URL = env("LLM_SERVICE_URL", cast=str, default="")
RAG_SERVICE_URL = env("RAG_SERVICE_URL", cast=str, default="")
DW_SERVICE_URL = env("DW_SERVICE_URL", cast=str, default="")

DEFAULT_REASONING_ENABLE = env("DEFAULT_REASONING_ENABLE", cast=str, default="false").lower() == "true"

def get_default_llm():
    return  ChatOllama(
        model="qwen3:8b",
        base_url=LLM_SERVICE_URL,
        reasoning=DEFAULT_REASONING_ENABLE,
        num_ctx=8192
    )

INTERNAL_DOCUMENTS_RAG_COLLECTION_NAME = env("INTERNAL_DOCUMENT_RAG_COLLECTION_NAME", cast=str, default="internal_documents")
DB_TABLE_SCHEMAS_RAG_COLLECTION_NAME = env("DB_TABLE_SCHEMAS_RAG_COLLECTION_NAME", cast=str, default="db_table_schemas")
