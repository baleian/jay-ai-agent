import sys
import requests


BASE_URL = "http://localhost:8000"


def get_collection_by_name(name: str):
    response = requests.get(f"{BASE_URL}/collections")
    response.raise_for_status()
    collections = response.json()

    filtered_collections = list(filter(lambda c: c["name"] == name, collections))
    if len(filtered_collections) == 0:
        raise ValueError(f"Not found collection named '{name}'")
    if len(filtered_collections) > 1:
        raise ValueError(f"Duplicated collection nameed '{name}'")
    return filtered_collections[0]


def document_search(collection_id: str, query: str, limit: int = 4):
    url = f"{BASE_URL}/collections/{collection_id}/documents/search"
    payload = {"query": query, "limit": limit}
    response = requests.post(url, json=payload)
    response.raise_for_status()
    documents = response.json()
    return documents


def test_db_table_schemas_search():
    print("==== TEST 'db_table_schemas' search (START) ====")
    collection = get_collection_by_name("db_table_schemas")
    collection_id = collection["uuid"]
    test_data = [
        ("How many accounts who choose issuance after transaction are staying in East Bohemia region?", "account, district"),
        ("How many accounts who have region in Prague are eligible for loans?", "account, loan, district"),
        ("가장 최근에 거래한 고객은?", "trans, client"),
        ("문제 없이 전액 상환된 대출 금액의 비율", "loan"),
        ("프라하 리전에는 몇개의 계정이 있나요?", "district, account"),
        ("1994년에 카드를 발급한 고객", "client, card, disp")
    ]
    for query, required_tables in test_data:
        print("-----")
        print("Query:", query)
        print("Required tables:", required_tables)
        print("Retrieved files:")
        results = document_search(collection_id=collection_id, query=query, limit=10)
        for result in results:
            filename, score = result["metadata"]["filename"], result["score"]
            print(filename, score)
    print("==== TEST 'db_table_schemas' search (FINISHED) ====")


def test_internal_documents_search():
    print("==== TEST 'internal_documents' search (START) ====")
    collection = get_collection_by_name("internal_documents")
    collection_id = collection["uuid"]
    test_data = [
        "웹 서버 접속 주소 알려줘",
        "사내 DB 비밀번호 뭐였지?",
        "우리 회사 휴가 정책",
        "1년 동안 사용 가능한 연차 개수 알려줘",
        "복지 포인트"
    ]
    for query in test_data:
        print("-----")
        print("Query:", query)
        print("Retrieved files:")
        results = document_search(collection_id=collection_id, query=query, limit=2)
        for result in results:
            filename, score = result["metadata"]["filename"], result["score"]
            print(filename, score)
    print("==== TEST 'internal_documents' search (FINISHED) ====")


# --- 메인 실행 로직 ---
def main():
    try:
        test_db_table_schemas_search()
        test_internal_documents_search()
    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
