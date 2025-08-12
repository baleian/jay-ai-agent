#!/bin/bash
set -e

EXIST_COLLECTIONS=$(curl -s -X GET http://localhost:8000/collections)

if ! curl -s -X GET "http://localhost:8000/collections" | jq -e 'length == 0' > /dev/null; then
    echo "Exist collections:"
    echo $EXIST_COLLECTIONS | jq
    echo "Deleting all exist collections..."
    echo $EXIST_COLLECTIONS | jq -r '.[].uuid' | tr -d '\r' | \
        xargs -P 4 -I {} curl -s -X DELETE "http://localhost:8000/collections/{}"
    if ! curl -s -X GET "http://localhost:8000/collections" | jq -e 'length == 0' > /dev/null; then
        echo "Deletion failed." >&2
        exit 1
    fi
fi

##### Build `db_table_schema` collection #####
echo "Creating 'db_table_schemas' collection"
COLLECTION=$(curl -s -X POST http://localhost:8000/collections \
-H "Content-Type: application/json" \
-d '{
    "name": "db_table_schemas",
    "metadata": {"description": "Collection for storing internal database schemas (DDL)."}
}')
echo "Created collection:"
echo $COLLECTION | jq

echo "Creating initial documents into 'db_table_schemas' collection..."
COLLECTION_ID=$(echo $COLLECTION | jq -r '.uuid')
DATA_DIR=scripts/data/collections/db_table_schemas
curl -s -X POST "http://localhost:8000/collections/$COLLECTION_ID/documents" \
-F "files=@$DATA_DIR/account.sql;type=text/plain" \
-F "files=@$DATA_DIR/card.sql;type=text/plain" \
-F "files=@$DATA_DIR/client.sql;type=text/plain" \
-F "files=@$DATA_DIR/disp.sql;type=text/plain" \
-F "files=@$DATA_DIR/district.sql;type=text/plain" \
-F "files=@$DATA_DIR/loan.sql;type=text/plain" \
-F "files=@$DATA_DIR/order.sql;type=text/plain" \
-F "files=@$DATA_DIR/trans.sql;type=text/plain" \
-F 'metadatas_json=[
    {"filename": "account.sql", "description": "Table containing customer account information"}, 
    {"filename": "card.sql", "description": "Table containing credit card information"},
    {"filename": "client.sql", "description": "Table containing client demographic information"},
    {"filename": "disp.sql", "description": "Table linking clients to accounts with specific rights (dispositions)"},
    {"filename": "district.sql", "description": "Table containing demographic and economic statistics for each district"},
    {"filename": "loan.sql", "description": "Table containing loan information for each account"},
    {"filename": "order.sql", "description": "Table containing payment order information"},
    {"filename": "trans.sql", "description": "Table containing detailed transaction records for each account"}
];charset=UTF-8' > /dev/null

echo "Created documents:"
curl -s -X GET "http://localhost:8000/collections/$COLLECTION_ID/documents" | jq


##### Build `internal_documents` collection #####
echo "Creating 'internal_documents' collection"
COLLECTION=$(curl -s -X POST http://localhost:8000/collections \
-H "Content-Type: application/json" \
-d '{
    "name": "internal_documents",
    "metadata": {"description": "Collection for storing internal database schemas (DDL)."}
}')
echo "Created collection:"
echo $COLLECTION | jq

echo "Creating initial documents into 'internal_documents' collection..."
COLLECTION_ID=$(echo $COLLECTION | jq -r '.uuid')
DATA_DIR=scripts/data/collections/internal_documents
curl -s -X POST "http://localhost:8000/collections/$COLLECTION_ID/documents" \
-F "files=@$DATA_DIR/시스템정보.txt;type=text/plain" \
-F "files=@$DATA_DIR/연차규정.pdf;type=application/pdf" \
-F 'metadatas_json=[
    {"filename": "시스템정보.txt", "description": "사내 데이터베이스 및 웹 서버와 같은 시스템에 대한 접속 정보"},
    {"filename": "연차규정.pdf", "description": "사내 연차 규정에 대한 내용"}
];charset=UTF-8' > /dev/null

echo "Created documents:"
curl -s -X GET "http://localhost:8000/collections/$COLLECTION_ID/documents" | jq
