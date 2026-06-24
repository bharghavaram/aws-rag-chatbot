import os

# these felt right after testing — reasoning in README and report.md
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 4

# all-MiniLM-L6-v2: fast on CPU, no API key needed, good enough for English legal text
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

HF_API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
LLM_MODEL = os.getenv("LLM_MODEL", "google/flan-t5-large")

_here = os.path.dirname(__file__)
PDF_PATH = os.path.join(_here, "..", "data", "AWS Customer Agreement.pdf")
VECTORSTORE_PATH = os.path.join(_here, "..", "vectorstore", "faiss_index")
DB_PATH = os.path.join(_here, "..", "analytics.db")
