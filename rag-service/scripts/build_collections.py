import requests
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 설정 ---
BASE_URL = "http://localhost:8000"
DATA_DIR_BASE = "scripts/data/collections"

# --- 헬퍼 함수 ---
def print_json(data):
    """JSON 데이터를 예쁘게 출력합니다."""
    print(json.dumps(data, indent=4, ensure_ascii=False))

def delete_collection(collection_id):
    """단일 컬렉션을 삭제하는 함수 (병렬 처리를 위함)"""
    url = f"{BASE_URL}/collections/{collection_id}"
    try:
        response = requests.delete(url)
        response.raise_for_status()
        print(f"Deleted collection: {collection_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to delete {collection_id}: {e}", file=sys.stderr)
        return False

def create_collection(name, description):
    """새로운 컬렉션을 생성하는 함수"""
    print(f"--- Creating '{name}' collection ---")
    url = f"{BASE_URL}/collections"
    payload = {"name": name, "metadata": {"description": description}}
    response = requests.post(url, json=payload)
    response.raise_for_status()
    collection_data = response.json()
    print("Created collection:")
    print_json(collection_data)
    return collection_data

def upload_documents(collection_id, data_dir, files_metadata):
    """지정된 컬렉션에 여러 문서를 업로드하는 함수"""
    print(f"Creating initial documents into '{data_dir}' collection...")
    url = f"{BASE_URL}/collections/{collection_id}/documents"
    
    # multipart/form-data 페이로드 준비
    multipart_files = []
    for file_info in files_metadata:
        file_path = os.path.join(data_dir, file_info["filename"])
        # 파일을 바이너리 모드로 열고, 파일명과 MIME 타입을 함께 전달
        multipart_files.append(
            ("files", (os.path.basename(file_path), open(file_path, "rb"), file_info["type"]))
        )
    
    metadata_str = json.dumps([
        {"filename": f["filename"], "description": f["description"]}
        for f in files_metadata
    ], ensure_ascii=False)

    # 데이터와 함께 요청 전송
    response = requests.post(url, files=multipart_files, data={"metadatas_json": metadata_str})
    response.raise_for_status()

    # 업로드된 파일 목록 확인
    print("Created documents:")
    docs_response = requests.get(f"{BASE_URL}/collections/{collection_id}/documents")
    docs_response.raise_for_status()
    print_json(docs_response.json())


# --- 메인 실행 로직 ---
def main():
    try:
        # 1. 기존 컬렉션 확인 및 삭제
        print("Checking for existing collections...")
        response = requests.get(f"{BASE_URL}/collections")
        response.raise_for_status()
        existing_collections = response.json()

        if existing_collections:
            print("Existing collections found:")
            print_json(existing_collections)
            print("Deleting all existing collections...")
            
            uuids_to_delete = [c["uuid"] for c in existing_collections]
            
            # ThreadPoolExecutor를 사용해 병렬로 삭제 (xargs -P 4와 유사)
            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(delete_collection, uuids_to_delete))

            # 삭제 후 확인
            final_check_response = requests.get(f"{BASE_URL}/collections")
            final_check_response.raise_for_status()
            if final_check_response.json():
                print("Error: Deletion failed. Some collections still exist.", file=sys.stderr)
                sys.exit(1)
            print("All collections deleted successfully.")
        else:
            print("No existing collections found.")

        # 2. 'db_table_schemas' 컬렉션 생성 및 문서 업로드
        db_schemas_collection = create_collection(
            name="db_table_schemas",
            description="Collection for storing internal database schemas (DDL)."
        )
        db_schemas_files = [
            {"filename": "account.sql", "type": "text/plain", "description": "Table containing customer account information"},
            {"filename": "card.sql", "type": "text/plain", "description": "Table containing credit card information"},
            {"filename": "client.sql", "type": "text/plain", "description": "Table containing client demographic information"},
            {"filename": "disp.sql", "type": "text/plain", "description": "Table linking clients to accounts with specific rights (dispositions)"},
            {"filename": "district.sql", "type": "text/plain", "description": "Table containing demographic and economic statistics for each district"},
            {"filename": "loan.sql", "type": "text/plain", "description": "Table containing loan information for each account"},
            {"filename": "order.sql", "type": "text/plain", "description": "Table containing payment order information"},
            {"filename": "trans.sql", "type": "text/plain", "description": "Table containing detailed transaction records for each account"}
        ]
        upload_documents(
            collection_id=db_schemas_collection["uuid"],
            data_dir=os.path.join(DATA_DIR_BASE, "db_table_schemas"),
            files_metadata=db_schemas_files
        )

        # 3. 'internal_documents' 컬렉션 생성 및 문서 업로드
        internal_docs_collection = create_collection(
            name="internal_documents",
            description="Collection for storing internal company documents."
        )
        internal_docs_files = [
            {"filename": "연차규정.pdf", "type": "application/pdf", "description": "사내 연차 규정에 대한 내용. Annual leave policy."},
            {"filename": "시스템정보.txt", "type": "text/plain", "description": "사내 데이터베이스 및 웹 서버와 같은 시스템에 대한 접속 정보. System access informations."}
        ]
        upload_documents(
            collection_id=internal_docs_collection["uuid"],
            data_dir=os.path.join(DATA_DIR_BASE, "internal_documents"),
            files_metadata=internal_docs_files
        )

    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()