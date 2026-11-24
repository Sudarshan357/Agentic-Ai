"""RAG over the uploaded papers: Chroma + nomic-embed-text (via Ollama).

Each set of papers gets its own Chroma collection, named after a hash of the
files. Uploading the same papers again reuses the existing vectors instead of
embedding them a second time.
"""

from __future__ import annotations

import os
import re
import threading

import chromadb
from langchain_chroma import Chroma

from memory import MEMORY_DIR, get_embeddings

CHROMA_DIR = os.path.join(MEMORY_DIR, "chroma")

CHUNK_WORDS = 120
CHUNK_OVERLAP = 30

_lock = threading.Lock()
_client = None


def _chroma_client():
    global _client
    with _lock:
        if _client is None:
            os.makedirs(CHROMA_DIR, exist_ok=True)
            _client = chromadb.PersistentClient(path=CHROMA_DIR)
        return _client


def collection_name(corpus: str) -> str:
    return f"papers-{corpus}"


def vector_store(corpus: str) -> Chroma:
    return Chroma(
        client=_chroma_client(),
        collection_name=collection_name(corpus),
        embedding_function=get_embeddings(),
        collection_metadata={"hnsw:space": "cosine"},
    )


def chunk_text(text: str, size: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split on sentence boundaries into chunks of about `size` words."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if s.strip()]
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for sentence in sentences:
        words = len(sentence.split())
        if current and count + words > size:
            chunks.append(" ".join(current).strip())
            # carry the tail over so facts that span a boundary are not lost
            tail: list[str] = []
            tail_count = 0
            for previous in reversed(current):
                tail_count += len(previous.split())
                tail.insert(0, previous)
                if tail_count >= overlap:
                    break
            current, count = tail, tail_count
        current.append(sentence.strip())
        count += words
    if current:
        chunks.append(" ".join(current).strip())
    return [" ".join(c.split()) for c in chunks if c.strip()]


def index_documents(documents: list[dict], corpus: str) -> dict:
    """Embed the papers into Chroma (once per corpus). Returns index stats."""
    store = vector_store(corpus)
    existing = store._collection.count()
    if existing:
        return {"collection": collection_name(corpus), "chunks": existing, "reused": True}

    texts: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    for doc in documents:
        for index, chunk in enumerate(chunk_text(doc["content"])):
            texts.append(chunk)
            metadatas.append({"source": doc["name"], "chunk": index})
            ids.append(f"{doc['name']}::{index}")

    if texts:
        store.add_texts(texts, metadatas=metadatas, ids=ids)
    return {"collection": collection_name(corpus), "chunks": len(texts), "reused": False}


def retrieve(corpus: str, query: str, k: int = 4) -> list[dict]:
    """Top-k passages for `query`, best first."""
    hits = vector_store(corpus).similarity_search_with_score(query, k=k)
    return [
        {
            "text": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "chunk": doc.metadata.get("chunk", 0),
            "distance": round(float(score), 3),
        }
        for doc, score in hits
    ]


def retrieve_many(corpus: str, queries: list[str], k: int = 4) -> list[dict]:
    """Union of several searches, de-duplicated, in document order."""
    seen: dict[tuple, dict] = {}
    for query in queries:
        for hit in retrieve(corpus, query, k=k):
            key = (hit["source"], hit["chunk"])
            if key not in seen or hit["distance"] < seen[key]["distance"]:
                seen[key] = hit
    return sorted(seen.values(), key=lambda h: (h["source"], h["chunk"]))


def format_passages(hits: list[dict]) -> str:
    return "\n\n".join(f"[{h['source']} · passage {h['chunk'] + 1}]\n{h['text']}" for h in hits)
