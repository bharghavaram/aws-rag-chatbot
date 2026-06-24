from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

import database
import rag

app = FastAPI(title="AWS Agreement Q&A")

# allow_origins=["*"] is fine for a local assignment — not for prod
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
            raise ValueError("Question is too long (limit: 2000 chars).")
        return v


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]
    answer_found: bool
    response_time_seconds: float


class IngestResponse(BaseModel):
    message: str
    pages_loaded: int
    chunks_created: int


@app.post("/ingest", response_model=IngestResponse)
def ingest():
    # run once before /ask — builds the FAISS index from the PDF
    try:
        res = rag.ingest_pdf()
        return IngestResponse(
            message="done",
            pages_loaded=res["pages_loaded"],
            chunks_created=res["chunks_created"],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
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
        answer_found=res["answer_found"],
        response_time_seconds=res["response_time"],
    )


@app.get("/analytics")
def analytics():
    try:
        return database.get_analytics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
