# AWS Customer Agreement RAG Chatbot

A simple RAG system for asking questions about the AWS Customer Agreement and getting answers backed by the actual document, with source page references.

Built for the Vestaff Junior AI Developer assignment.

## Why I built it this way

I wanted to keep it simple and local-friendly — no paid APIs required to run it. The HuggingFace free tier handles the LLM, embeddings run on CPU, and the vector store is just a file on disk. The goal was a working system, not an impressive dependency list.

## What it does

- Parses and indexes the AWS Customer Agreement PDF using FAISS + sentence-transformers
- Answers questions by finding the most relevant chunks and passing them to an LLM
- Returns the answer with source page references
- Logs every question to SQLite (most asked, no-answer rate, avg latency)
- Streamlit frontend with a chat page and an analytics dashboard

## Tech stack

- **Backend**: FastAPI + LangChain
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2) — runs locally, no API key
- **Vector store**: FAISS
- **LLM**: HuggingFace Inference API (flan-t5-large by default, free tier)
- **Database**: SQLite
- **Frontend**: Streamlit

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/bharghavaram/aws-rag-chatbot.git
cd aws-rag-chatbot
pip install -r requirements.txt
```

### 2. Get a free HuggingFace token

Go to https://huggingface.co/settings/tokens and create a token (read access is enough).

```bash
# Mac / Linux
export HUGGINGFACEHUB_API_TOKEN=your_token_here

# Windows PowerShell
$env:HUGGINGFACEHUB_API_TOKEN="your_token_here"
```

### 3. Start the backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Ingest the PDF

Run this once. It processes the PDF and saves the FAISS index to disk.

```bash
curl -X POST http://localhost:8000/ingest
```

Or click the **Ingest PDF** button in the Streamlit sidebar.

### 5. Start the frontend (new terminal)

```bash
cd frontend
streamlit run app.py
```

Open http://localhost:8501

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest` | Parse and index the PDF |
| POST | `/ask` | Ask a question, returns answer + sources |
| GET | `/analytics` | Usage stats from SQLite |
| GET | `/health` | Health check |

Swagger docs: http://localhost:8000/docs

### Example

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Can AWS access my data?"}'
```

```json
{
  "answer": "AWS will not access or use Your Content except as necessary to maintain or provide the Services...",
  "sources": [{"page": 2, "snippet": "You may specify the AWS regions in which..."}],
  "answer_found": true,
  "response_time_seconds": 1.52
}
```

---

## Chunking decisions

I settled on `chunk_size=1000` with `chunk_overlap=200`.

The AWS Agreement is organized around numbered clauses, and most of them are between 400 and 900 characters. At 1000 chars, a chunk almost always holds exactly one complete clause. Smaller chunks (tried 400) kept cutting clauses mid-sentence — the LLM was receiving fragments with no surrounding context and the answers got noticeably worse. Larger chunks (2000+) started mixing unrelated sections, which hurt precision.

The 200-char overlap handles cases where a clause references the one before it — common in legal docs.

For retrieval I'm using `top_k=4`. Two chunks wasn't enough for broad questions like "What are AWS's responsibilities?" which spans several sub-sections. Six added noise. Four gave the best balance.

---

## Current limitations

- Chat history is in-memory only — refresh the page and it's gone
- No similarity score threshold: if retrieved chunks are off-topic the LLM still gets called (the prompt tells it to say it doesn't know, but it's not always reliable)
- flan-t5-large sometimes gives short or incomplete answers on complex multi-clause questions
- Can't upload a different PDF without restarting the backend and re-ingesting
- The `/analytics` endpoint has no auth — fine for local use only
- HuggingFace free tier has rate limits, so running `seed_queries.py` too fast will hit 503s

---

## Fill analytics with test data

After ingesting, run the seed script to send 30 sample questions:

```bash
cd backend
python seed_queries.py
```

---

## Swap the LLM

Default is `google/flan-t5-large`. To use something else:

```bash
export LLM_MODEL=mistralai/Mistral-7B-Instruct-v0.2
```

Any HuggingFace Hub model should work as long as your token has access to it.

---

## Folder structure

```
aws-rag-chatbot/
├── backend/
│   ├── main.py            # FastAPI routes
│   ├── rag.py             # ingestion + retrieval + generation
│   ├── database.py        # SQLite helpers
│   ├── config.py          # paths and defaults
│   └── seed_queries.py    # test query script
├── frontend/
│   └── app.py             # Streamlit UI
├── data/
│   └── AWS Customer Agreement.pdf
├── vectorstore/           # FAISS index saved here after /ingest
├── docs/
│   └── decisions.md       # architecture notes
├── requirements.txt
└── README.md
```
