import requests
from typing import List
from functools import cache

from app import config


@cache
def get_collection_id_by_name(name: str) -> str:
    response = requests.get(f"{config.RAG_SERVICE_URL}/collections")
    response.raise_for_status()
    collections = response.json()

    filtered_collections = list(filter(lambda c: c["name"] == name, collections))
    if len(filtered_collections) == 0:
        raise ValueError(f"Not found collection named '{name}'")
    if len(filtered_collections) > 1:
        raise ValueError(f"Duplicated collection nameed '{name}'")
    return filtered_collections[0]["uuid"]


def document_search(collection_id: str, query: str, limit: int = 4) -> List[dict]:
    url = f"{config.RAG_SERVICE_URL}/collections/{collection_id}/documents/search"
    payload = {"query": query, "limit": limit}
    response = requests.post(url, json=payload)
    response.raise_for_status()
    documents = response.json()
    return documents
