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
            f"PDF not found at {PDF_PATH}. "
            "Put 'AWS Customer Agreement.pdf' in the data/ folder."
        )

    loader = PyPDFLoader(PDF_PATH)
    pages = loader.load()

    # chunk_size=1000 because most clauses in this doc are 400-900 chars.
    # keeping one clause per chunk made retrieval noticeably better.
    # overlap=200 — legal text often references the clause above, so some
    # overlap reduces the chance of losing that context at a boundary.
    # I tried 400-char chunks first and retrieval was noticeably worse —
    # the LLM kept getting fragments with no surrounding context.
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

    _qa_chain = None  # rebuild on next /ask call

    return {
        "pages_loaded": len(pages),
        "chunks_created": len(chunks),
    }


def _load_store():
    global _vectorstore
    if _vectorstore is not None:
        return
    idx = VECTORSTORE_PATH + ".faiss"
    if not os.path.exists(idx):
        raise RuntimeError("No index on disk — call POST /ingest first.")
    emb = _get_embeddings()
    _vectorstore = FAISS.load_local(
        VECTORSTORE_PATH, emb, allow_dangerous_deserialization=True
    )


def _build_chain():
    global _qa_chain
    if _qa_chain is not None:
        return _qa_chain

    _load_store()

    if not HF_API_TOKEN:
        raise RuntimeError(
            "HUGGINGFACEHUB_API_TOKEN not set. "
            "Get a free token from https://huggingface.co/settings/tokens"
        )

    # keeping the prompt tight — if I give the model too much room it starts
    # hallucinating things that sound plausible but aren't in the agreement
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""Answer the question using only the context below.
If the answer is not in the context, say: "I could not find an answer to this question in the AWS Customer Agreement."

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

    # k=4: tried 2 (too few for broad questions) and 6 (added noise).
    # "What are AWS's responsibilities?" spans sections 1.1–1.6, so 2 chunks wasn't enough.
    # TODO: add a similarity score threshold so we skip the LLM when chunks are irrelevant
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

    chain = _build_chain()
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

    # compact summary for the DB row — storing full chunks would bloat the table
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
