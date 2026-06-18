from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

import database
import rag

app = FastAPI(
    title="AWS Customer Agreement Q&A",
    description="RAG pipeline for querying the AWS Customer Agreement PDF",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()


class AskRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        if len(v) > 2000:
            raise ValueError("Question is too long (limit: 2000 characters).")
        return v


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]
    source_summary: str
    answer_found: bool
    response_time_seconds: float


class IngestResponse(BaseModel):
    message: str
    pages_loaded: int
    chunks_created: int
    chunk_size: int
    chunk_overlap: int


@app.post("/ingest", response_model=IngestResponse)
def ingest():
    """Process the PDF and build the FAISS index. Run this once before using /ask."""
    try:
        res = rag.ingest_pdf()
        return IngestResponse(message="PDF ingested and indexed successfully.", **res)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """Run the RAG pipeline for a question. Logs every request to SQLite."""
    try:
        res = rag.answer_question(body.question)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    database.log_query(
        question=body.question,
        answer=res["answer"],
        source=res["source_summary"],
        answer_found=res["answer_found"],
        response_time=res["response_time"],
    )

    return AskResponse(
        answer=res["answer"],
        sources=res["sources"],
        source_summary=res["source_summary"],
        answer_found=res["answer_found"],
        response_time_seconds=res["response_time"],
    )


@app.get("/analytics")
def analytics():
    """Return usage stats pulled from the SQL database."""
    try:
        return database.get_analytics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
