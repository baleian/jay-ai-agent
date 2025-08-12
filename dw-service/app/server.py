import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI()

DB_PATH = "data/financial.sqlite"


class QueryRequest(BaseModel):
    query: str


@app.post("/query")
def execute_query(request: QueryRequest):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(request.query)
        rows = cursor.fetchall()
        
        result = [dict(row) for row in rows]
        conn.close()
        
        return {"data": result}
        
    except sqlite3.Error as e:
        raise HTTPException(status_code=400, detail=f"SQL Error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server Error: {e}")


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.server:app", host="0.0.0.0", port=8080)
