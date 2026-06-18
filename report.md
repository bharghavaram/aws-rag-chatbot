# Technical Report
## RAG-based Document Q&A System

**Assignment**: Junior AI Developer | Vestaff

---

### 1. Overview

This project is a question-answering system built around the AWS Customer Agreement PDF. The user can ask natural language questions through a web interface and get answers grounded in the document, with references to the source pages. Every query is logged to a SQLite database for analytics.

---

### 2. System Design

The pipeline has four main stages:

**Ingestion**
The PDF is loaded with LangChain's PyPDFLoader, which extracts text page by page and preserves page number metadata. The text is split into overlapping chunks using RecursiveCharacterTextSplitter. Each chunk is then embedded using a local HuggingFace model and stored in a FAISS index on disk.

**Retrieval**
When a question comes in, it's embedded using the same model and compared against all stored chunks. The top-k most similar chunks are returned.

**Generation**
The retrieved chunks are inserted into a prompt template along with the question and sent to an LLM. The prompt explicitly tells the model to only use the provided context and to admit when it doesn't know rather than making something up.

**Logging**
Every request — question, answer, source, response time, and whether an answer was found — is written to a SQLite table. This powers the /analytics endpoint.

---

### 3. Chunking

**chunk_size = 1000, chunk_overlap = 200**

The AWS Customer Agreement is structured around numbered clauses. I measured a sample of them and found most fall between 400 and 900 characters. A chunk size of 1000 captures one full clause in most cases without pulling in unrelated content from adjacent sections.

I tested smaller chunks (400 chars) and found retrieval quality dropped significantly — the chunks were too small to be self-contained and the LLM kept receiving fragments that didn't have enough context to produce a good answer. Larger chunks (2000 chars) bundled together unrelated clauses, which confused similarity search and reduced precision.

The 200-char overlap prevents important content from being cut off at chunk boundaries. Legal text often has clauses that reference the preceding clause ("as described in Section 4.1 above"), so having some overlap between adjacent chunks reduces the risk of that context being lost.

The splitter uses separators `["\n\n", "\n", ". "]` — it prefers paragraph breaks over line breaks over sentence boundaries, which keeps each chunk semantically coherent.

---

### 4. Embeddings

I used `sentence-transformers/all-MiniLM-L6-v2`. It runs on CPU without any API key, is well-tested for English semantic similarity, and is fast enough that the one-time ingestion step completes in under a minute on a standard laptop.

---

### 5. Vector Store

FAISS was chosen over ChromaDB because it doesn't require a separate server process. The index is saved to disk after ingestion and loaded on startup. At the scale of this document (under 200 chunks), flat exact search is fast enough — queries come back in under 50ms.

---

### 6. Retrieval: top-k = 4

I chose k=4 after testing with different values. The question "What are AWS's responsibilities?" is a good benchmark — the full answer spans sections 1.1 through 1.6 of the document. With k=2 the response was often incomplete. With k=6 the retrieved chunks started including content from unrelated sections, which introduced noise into the prompt. k=4 worked best across both broad and specific questions.

---

### 7. Language Model

I used `google/flan-t5-large` via the HuggingFace Inference API. It's available on the free tier, follows instruction prompts reliably, and doesn't require any local GPU. The model is configurable through an environment variable so it can be swapped without touching the code.

The prompt template is strict about not hallucinating:

> "If the answer isn't in the context, say: 'I could not find an answer to this question in the AWS Customer Agreement.'"

After getting the response, the code checks whether it contains any "not found" phrasing and sets the `answer_found` flag accordingly. This flag is logged to SQL and surfaced in the analytics dashboard.

---

### 8. SQL Schema

```sql
CREATE TABLE queries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    question      TEXT NOT NULL,
    answer        TEXT,
    source        TEXT,
    answer_found  INTEGER DEFAULT 1,
    response_time FLOAT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`answer_found` is stored as 0/1 (SQLite doesn't have a boolean type). `source` holds a compact text summary of the source pages rather than the full chunk content to keep the rows small. `response_time` is in seconds as a float so `AVG()` gives meaningful results.

---

### 9. Frontend

The Streamlit app runs as a separate process and communicates with the FastAPI backend over HTTP. Two pages:

- **Chat** — conversation interface, shows answers with expandable source references and response time
- **Analytics** — summary metrics, most-asked questions table, daily query volume bar chart, and a table of questions where no answer was found

---

### 10. What I'd improve

- Switch to a local model via Ollama to remove the dependency on the HuggingFace Inference API rate limits
- Add a similarity score threshold so the system skips the LLM entirely when retrieved chunks aren't relevant enough, instead of relying on prompt instructions to catch it
- Support uploading multiple documents with per-document filtering
- Add basic auth to the analytics endpoint before deploying anywhere public
