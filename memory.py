"""Short-term and long-term memory for the research graph.

Short-term (thread) memory
    A LangGraph checkpointer saved in SQLite. Every run is tied to a thread_id.
    The graph state of that thread is saved after every step, so a run can pause
    for human approval and resume later. The `messages` channel keeps growing
    across runs on the same thread, so the agents can see what was said earlier
    in the conversation.

Long-term memory
    A LangGraph SqliteStore. It outlives threads. The graph writes two things
    into it:
      ("lessons",)              mistakes caught by the fact checker, the guard
                                or the human reviewer, searchable by meaning
                                (nomic-embed-text embeddings)
      ("summaries", corpus_id)  approved summaries for a given set of papers
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time

from langchain_ollama import OllamaEmbeddings
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore

HERE = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.environ.get("RESEARCH_MEMORY_DIR", os.path.join(HERE, "memory_data"))
CHECKPOINT_DB = os.path.join(MEMORY_DIR, "checkpoints.sqlite")
STORE_DB = os.path.join(MEMORY_DIR, "store.sqlite")

EMBED_MODEL = "nomic-embed-text"
EMBED_DIMS = 768

LESSONS_NS = ("lessons",)

_lock = threading.Lock()
_checkpointer: SqliteSaver | None = None
_store: SqliteStore | None = None
_embeddings: OllamaEmbeddings | None = None


def get_embeddings() -> OllamaEmbeddings:
    """Shared nomic-embed-text client, used by both the store and Chroma."""
    global _embeddings
    with _lock:
        if _embeddings is None:
            _embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        return _embeddings


def get_checkpointer() -> SqliteSaver:
    """Short-term memory: one SQLite-backed checkpointer for the whole process."""
    global _checkpointer
    with _lock:
        if _checkpointer is None:
            os.makedirs(MEMORY_DIR, exist_ok=True)
            conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
            _checkpointer = SqliteSaver(conn)
            _checkpointer.setup()
        return _checkpointer


def get_store() -> SqliteStore:
    """Long-term memory: a SQLite store with semantic search over lessons."""
    global _store
    embeddings = get_embeddings()
    with _lock:
        if _store is None:
            os.makedirs(MEMORY_DIR, exist_ok=True)
            # The store manages its own transactions, so autocommit mode is required.
            conn = sqlite3.connect(STORE_DB, check_same_thread=False, isolation_level=None)
            _store = SqliteStore(
                conn,
                index={"dims": EMBED_DIMS, "embed": embeddings, "fields": ["lesson"]},
            )
            _store.setup()
        return _store


def corpus_id(documents: list[dict]) -> str:
    """Stable id for a set of uploaded papers (same files -> same id)."""
    digest = hashlib.sha1()
    for doc in sorted(documents, key=lambda d: d["name"]):
        digest.update(doc["name"].encode("utf-8"))
        digest.update(doc["content"].encode("utf-8"))
    return digest.hexdigest()[:16]


def _key(text: str) -> str:
    return hashlib.sha1(" ".join(text.lower().split()).encode("utf-8")).hexdigest()[:20]


def recall_lessons(store, query: str, limit: int = 4) -> list[dict]:
    """Lessons from earlier runs that are closest in meaning to `query`."""
    try:
        items = store.search(LESSONS_NS, query=query or None, limit=limit)
    except Exception:  # noqa: BLE001 - memory must never break a run
        return []
    return [
        {**item.value, "score": round(item.score, 3) if item.score is not None else None}
        for item in items
    ]


def save_lesson(store, lesson: str, kind: str, example: str = "") -> None:
    """Write one lesson. The same lesson twice only updates its counter."""
    key = _key(lesson)
    existing = store.get(LESSONS_NS, key)
    seen = (existing.value.get("times_seen", 0) if existing else 0) + 1
    store.put(
        LESSONS_NS,
        key,
        {
            "lesson": lesson,
            "kind": kind,
            "example": example,
            "times_seen": seen,
            "updated": time.strftime("%Y-%m-%d %H:%M"),
        },
    )


def save_summary(store, corpus: str, thread_id: str, summary: str, status: str) -> None:
    store.put(
        ("summaries", corpus),
        f"{thread_id}-{int(time.time())}",
        {
            "summary": summary,
            "status": status,
            "thread_id": thread_id,
            "saved": time.strftime("%Y-%m-%d %H:%M"),
        },
        index=False,
    )


def previous_summaries(store, corpus: str, limit: int = 3) -> list[dict]:
    try:
        items = store.search(("summaries", corpus), limit=limit)
    except Exception:  # noqa: BLE001
        return []
    return [item.value for item in items]


def all_lessons(store, limit: int = 50) -> list[dict]:
    try:
        return [item.value for item in store.search(LESSONS_NS, limit=limit)]
    except Exception:  # noqa: BLE001
        return []


def clear_long_term(store) -> int:
    """Delete every lesson and saved summary. Returns how many items went."""
    removed = 0
    for namespace in store.list_namespaces():
        for item in store.search(namespace, limit=1000):
            store.delete(namespace, item.key)
            removed += 1
    return removed
