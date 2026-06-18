# AWS Customer Agreement RAG Chatbot

A simple RAG (Retrieval-Augmented Generation) system that lets you ask questions about the AWS Customer Agreement and get answers backed by the actual document — with source page references included.

Built for the Vestaff Junior AI Developer assignment.

## What it does

- Parses and indexes the AWS Customer Agreement PDF using FAISS + sentence-transformers
- Answers questions by finding the most relevant chunks and passing them to an LLM
- Returns the answer along with which pages it pulled from
- Logs every question to SQLite for analytics (most asked, no-answer rate, avg latency)
- Includes a Streamlit frontend with a chat page and an analytics dashboard

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

This only needs to run once. It processes the PDF and saves the FAISS index to disk.

```bash
curl -X POST http://localhost:8000/ingest
```

Or click the **Ingest PDF** button in the Streamlit sidebar.

### 5. Start the frontend (in a new terminal)

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
| GET | `/analytics` | Usage stats from the SQL database |
| GET | `/health` | Health check |

Interactive docs: http://localhost:8000/docs

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

The AWS Agreement is organized around numbered clauses, and most of them are between 400 and 900 characters. At 1000 chars, a chunk almost always holds exactly one complete clause. Smaller chunks (tried 400) kept cutting clauses mid-sentence and made retrieval noticeably worse. Larger chunks (2000+) started mixing unrelated sections into the same chunk, which hurt precision.

The 200-char overlap handles the cases where a clause continues from or references the one before it — common in legal docs.

For retrieval I'm using `top_k=4`. Two chunks wasn't enough for broad questions like "What are AWS's responsibilities?" which spans several sub-sections. Six added noise. Four gave the best balance.

---

## Fill analytics with test data

After ingesting, run the seed script to send 30 sample questions (a mix of answerable and out-of-scope):

```bash
cd backend
python seed_queries.py
```

---

## Swap the LLM

The default model is `google/flan-t5-large`. To use something else:

```bash
export LLM_MODEL=mistralai/Mistral-7B-Instruct-v0.2
```

Any model on HuggingFace Hub should work. Make sure your token has access to it.

---

## Folder structure

```
aws-rag-chatbot/
├── backend/
│   ├── main.py            # FastAPI app
│   ├── rag.py             # RAG pipeline
│   ├── database.py        # SQLite helpers
│   ├── config.py          # Settings and file paths
│   └── seed_queries.py    # Test query script
├── frontend/
│   └── app.py             # Streamlit UI
├── data/
│   └── AWS Customer Agreement.pdf
├── vectorstore/           # FAISS index saved here
├── requirements.txt
└── README.md
```
