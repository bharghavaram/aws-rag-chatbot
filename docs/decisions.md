# Architecture Notes

Quick writeup of the choices I made and why — mostly for my own reference.

## Why FastAPI instead of Flask

Needed async-friendly request handling and automatic request/response validation via Pydantic. Flask would've worked but I'd have had to wire up marshmallow or something similar manually. FastAPI also generates Swagger docs for free, which is useful for testing the `/ask` endpoint without Streamlit running.

## Why not LangGraph or a proper agent framework

I looked at LangGraph briefly but the overhead felt unnecessary for a single-document Q&A system. This is a linear pipeline: retrieve → generate → log. No branching, no tool calls, no multi-step reasoning. Adding an orchestration framework would have made it harder to understand what's actually happening.

## Why FAISS instead of ChromaDB

ChromaDB requires running a separate server process. FAISS saves to a couple of files on disk and loads in one line. At this scale (under 200 chunks) there's no performance difference. The simpler option wins.

## Why all-MiniLM-L6-v2

Fast on CPU, no API key, well-tested for English semantic similarity. I looked at `all-mpnet-base-v2` which benchmarks slightly better but takes about 3x longer to embed. For this document size the speed difference on ingestion doesn't matter, but for a larger corpus it would. I kept the faster one.

## Why flan-t5-large as the default LLM

It's on the HuggingFace free tier, follows instruction prompts reliably, and doesn't need a GPU. The outputs are sometimes short but they stay grounded in the context — it doesn't hallucinate much. Mistral or Llama would give better answers but require a higher-tier token. Making it configurable via env var means it's easy to swap.

## Why SQLite

It's zero-config and the analytics queries are simple aggregations. I briefly considered writing to a JSON file but SQLite is easier to query and doesn't have concurrency issues when multiple requests come in.

## Chunking — chunk_size=1000, overlap=200

Explained in detail in README and report.md. Short version: the AWS Agreement clauses fit in ~600-900 chars, so 1000 keeps one clause per chunk. 200 overlap because clauses often reference each other.

## TODO / things I'd change with more time

- [ ] Add a similarity threshold so the LLM isn't called when retrieved chunks are clearly off-topic
- [ ] Switch to a local Ollama model to remove the HuggingFace rate limit dependency
- [ ] Add session persistence — right now chat history disappears on page refresh
- [ ] Support ingesting multiple PDFs with per-document filtering
- [ ] Add basic auth to `/analytics` before putting this anywhere public
