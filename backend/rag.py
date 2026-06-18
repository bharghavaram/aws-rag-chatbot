import os
import time
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.llms import HuggingFaceHub
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

from config import (
    CHUNK_SIZE, CHUNK_OVERLAP, TOP_K,
    EMBEDDING_MODEL, PDF_PATH, VECTORSTORE_PATH,
    HF_API_TOKEN, LLM_MODEL
)

_vectorstore: Optional[FAISS] = None
_qa_chain = None


def _get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def ingest_pdf():
    global _vectorstore, _qa_chain

    if not os.path.exists(PDF_PATH):
        raise FileNotFoundError(
            f"Could not find PDF at {PDF_PATH}. "
            "Place 'AWS Customer Agreement.pdf' inside the data/ folder and try again."
        )

    loader = PyPDFLoader(PDF_PATH)
    pages = loader.load()

    # chunk_size=1000 works well for this doc — most clauses fit in ~600-900 chars,
    # so 1000 keeps each clause in one chunk without mixing unrelated sections.
    # overlap=200 because some clauses reference the one above them so I don't
    # want important text getting cut at the boundary.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(pages)

    embeddings = _get_embeddings()
    _vectorstore = FAISS.from_documents(chunks, embeddings)

    os.makedirs(os.path.dirname(VECTORSTORE_PATH), exist_ok=True)
    _vectorstore.save_local(VECTORSTORE_PATH)

    _qa_chain = None  # force rebuild on next question

    return {
        "pages_loaded": len(pages),
        "chunks_created": len(chunks),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "vectorstore_path": VECTORSTORE_PATH,
    }


def _load_store():
    global _vectorstore
    if _vectorstore is not None:
        return
    idx = VECTORSTORE_PATH + ".faiss"
    if not os.path.exists(idx):
        raise RuntimeError("No index found — please call POST /ingest first.")
    emb = _get_embeddings()
    _vectorstore = FAISS.load_local(VECTORSTORE_PATH, emb, allow_dangerous_deserialization=True)


def _get_chain():
    global _qa_chain
    if _qa_chain is not None:
        return _qa_chain

    _load_store()

    if not HF_API_TOKEN:
        raise RuntimeError(
            "HUGGINGFACEHUB_API_TOKEN is missing. "
            "Get a free token from https://huggingface.co/settings/tokens and set it as an env variable."
        )

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""You are a helpful assistant that answers questions about the AWS Customer Agreement.
Only use the information in the context provided below. Do not use any prior knowledge.
If the answer isn't in the context, say: "I could not find an answer to this question in the AWS Customer Agreement."

Context:
{context}

Question: {question}

Answer:"""
    )

    llm = HuggingFaceHub(
        repo_id=LLM_MODEL,
        huggingfacehub_api_token=HF_API_TOKEN,
        model_kwargs={"temperature": 0.1, "max_new_tokens": 512},
    )

    # top_k=4: tried 2 (too few, missed multi-section answers) and 6 (added noise).
    # 4 gave the best results on questions like "What are AWS responsibilities?"
    # which spans sections 1.1 through 1.6.
    retriever = _vectorstore.as_retriever(search_kwargs={"k": TOP_K})

    _qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt},
    )
    return _qa_chain


def answer_question(question: str) -> dict:
    t0 = time.time()

    chain = _get_chain()
    result = chain.invoke({"query": question})

    elapsed = round(time.time() - t0, 3)
    answer = result["result"].strip()

    no_answer_phrases = [
        "i could not find",
        "not present in the context",
        "not found in",
        "no information",
    ]
    found = not any(p in answer.lower() for p in no_answer_phrases)

    sources = []
    for doc in result.get("source_documents", []):
        pg = doc.metadata.get("page", "?")
        snippet = doc.page_content[:300].replace("\n", " ").strip()
        sources.append({
            "page": pg + 1 if isinstance(pg, int) else pg,
            "snippet": snippet,
        })

    src_summary = "; ".join(
        f"Page {s['page']}: {s['snippet'][:80]}..." for s in sources[:2]
    )

    return {
        "answer": answer,
        "sources": sources,
        "source_summary": src_summary,
        "answer_found": found,
        "response_time": elapsed,
    }
