"""Graph nodes: the supervisor, its three agents, the human-approval step and finalize.

Agents
    summarizer    writes / rewrites the summary from RAG passages + memory
    fact_checker  judges each claim against passages retrieved for that claim
    guard         deterministic safety checks the LLM cannot argue with
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.store.base import BaseStore
from langgraph.types import interrupt

import memory
import rag
from prompts import (
    FACT_CHECK_CLAIM,
    FACT_CHECK_SYSTEM,
    MEMORY_BLOCK,
    SUMMARIZER_FIRST_PASS,
    SUMMARIZER_REVISION,
    SUMMARIZER_SYSTEM,
)
from state import ResearchState


_LLM_CACHE: dict[tuple, ChatOllama] = {}


def get_llm(
    model: str = "qwen2.5:3b",
    temperature: float = 0.3,
    num_predict: int = 512,
) -> ChatOllama:
    """Cached ChatOllama client. Ollama must be running locally."""
    key = (model, temperature, num_predict)
    if key not in _LLM_CACHE:
        _LLM_CACHE[key] = ChatOllama(
            model=model,
            temperature=temperature,
            num_predict=num_predict,
            num_ctx=8192,
        )
    return _LLM_CACHE[key]


def _ask(
    model: str,
    system: str,
    user: str,
    temperature: float = 0.3,
    num_predict: int = 512,
) -> str:
    """Single-turn call to the local model."""
    llm = get_llm(model, temperature, num_predict)
    response = llm.invoke([("system", system), ("human", user)])
    return (response.content or "").strip()


def _trace(
    state: ResearchState,
    node: str,
    title: str,
    status: str,
    body: str,
    payload: dict[str, Any] | None = None,
) -> list:
    events = list(state.get("trace", []))
    events.append(
        {
            "step": len(events) + 1,
            "node": node,
            "title": title,
            "status": status,
            "iteration": state.get("iteration", 0),
            "body": body.strip(),
            "payload": payload or {},
        }
    )
    return events


def _log(state: ResearchState, node: str, label: str, status: str) -> list:
    entries = list(state.get("node_log", []))
    entries.append(
        {
            "node": node,
            "label": label,
            "status": status,
            "iteration": state.get("iteration", 0),
        }
    )
    return entries


SUPPORTED_SUFFIXES = (".txt", ".pdf")


def is_supported_source(name: str) -> bool:
    return name.lower().endswith(SUPPORTED_SUFFIXES)


def extract_text(path: str) -> str:
    """Plain text of one uploaded source, whatever its format."""
    if path.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise RuntimeError(
                "Reading PDF sources needs pypdf. Install it with: pip install pypdf"
            ) from exc

        reader = PdfReader(path)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n\n".join(p for p in pages if p).strip()
        if not text:
            raise ValueError(
                f"No text could be extracted from {os.path.basename(path)}. "
                "It is probably a scanned image; upload a text-based PDF or a .txt file."
            )
        return text

    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read().strip()


def read_source(state: ResearchState) -> dict:
    """Load the selected source files into the graph state. No LLM work."""
    sources_dir = state.get("sources_dir", "sources")

    if not os.path.isdir(sources_dir):
        return {
            "trace": _trace(
                state,
                "read_source",
                "READ SOURCE NODE",
                "error",
                f"Sources folder not found: {sources_dir}",
            ),
            "node_log": _log(state, "read_source", "READ SOURCE", "error"),
        }

    names: list[str] = []
    documents: list[dict] = []
    blocks: list[str] = []

    wanted = set(state.get("selected_sources") or [])
    found = sorted(f for f in os.listdir(sources_dir) if is_supported_source(f))
    skipped = [f for f in found if wanted and f not in wanted]

    for name in [f for f in found if not wanted or f in wanted]:
        content = extract_text(os.path.join(sources_dir, name))
        names.append(name)
        documents.append({"name": name, "content": content, "words": len(content.split())})
        blocks.append(f"[{name}]\n{content}")

    source_content = "\n\n".join(blocks)

    body = "\n".join(f"  OK   Loaded {name}" for name in names)
    if skipped:
        body += "\n" + "\n".join(f"  --   Skipped {name} (not selected)" for name in skipped)
    body += (
        f"\n\nTotal sources loaded: {len(names)}"
        f"\nTotal words: {sum(doc['words'] for doc in documents)}"
        f"\nSource content successfully added to graph state."
    )

    return {
        "sources": names,
        "source_documents": documents,
        "source_content": source_content,
        "trace": _trace(
            state, "read_source", "READ SOURCE NODE", "completed", body, {"files": names}
        ),
        "node_log": _log(state, "read_source", "READ SOURCE", "completed"),
    }


_SUBJECT_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "their", "there",
    "its", "was", "were", "are", "have", "has", "had", "been", "being",
    "which", "when", "where", "what", "how", "why", "than", "then", "also",
    "these", "those", "such", "into", "over", "under", "between", "across",
    "about", "study", "studies", "research", "paper", "papers", "analysis",
    "title", "source", "type", "authors", "report", "reports", "data",
    "results", "findings", "percent", "per", "cent", "not", "but", "can",
    "may", "will", "would", "could", "should", "more", "most", "less",
    "least", "each", "every", "all", "some", "any", "one", "two", "three",
}

_ENVIRONMENT_CUES = (
    "environment", "emission", "carbon", "climate", "pollution", "ecological",
    "greenhouse", "sustainab", "biodiversity", "energy", "lifecycle",
)


def _content_words(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", text.lower())
    return [w for w in words if w not in _SUBJECT_STOPWORDS]


def _subject_from_sources(documents: list[dict], source_content: str) -> str:
    """Name what the uploaded papers are about, for the injected claim."""
    titles = " ".join(
        (doc.get("content", "").splitlines() or [""])[0].replace("TITLE:", " ")
        for doc in documents
    )
    words = _content_words(titles) * 3 + _content_words(source_content)
    if not words:
        return "the subject of these sources"

    bigrams = Counter(
        f"{first} {second}" for first, second in zip(words, words[1:])
    )
    phrase, count = bigrams.most_common(1)[0] if bigrams else ("", 0)
    if count >= 4:
        return phrase

    unigrams = Counter(words)
    return unigrams.most_common(1)[0][0] if unigrams else "the subject of these sources"


def build_demo_overclaim(documents: list[dict], source_content: str) -> str:
    """The one deliberate over-claim injected into the first summary."""
    subject = _subject_from_sources(documents, source_content)
    subject = subject[0].upper() + subject[1:] if subject else "This subject"

    haystack = source_content.lower()
    if any(cue in haystack for cue in _ENVIRONMENT_CUES):
        return f"{subject} have zero environmental impact."
    return f"{subject} have zero drawbacks and work perfectly in every situation."


def _clean_summary(text: str) -> str:
    """Strip preambles and markdown fences the small model sometimes adds."""
    text = re.sub(r"^```[a-z]*\n?|```$", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(
        r"^(here is|here's|summary|research summary)\b[^\n:]*:\s*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )
    return " ".join(text.split()).strip()


_OVERCLAIM_PATTERNS = [
    (r"zero\s+drawbacks?", "claims there are zero drawbacks"),
    (r"no\s+drawbacks?", "claims there are no drawbacks"),
    (r"no\s+downsides?", "claims there are no downsides"),
    (r"no\s+limitations?\b", "claims there are no limitations"),
    (r"without\s+(?:any\s+)?limitations?", "claims there are no limitations"),
    (r"zero\s+(?:environmental\s+)?impact", "claims zero impact overall"),
    (r"no\s+(?:environmental\s+)?impact\b", "claims no impact overall"),
    (r"completely\s+(?:clean|safe|effective|reliable)", "uses absolute wording"),
    (r"entirely\s+(?:clean|safe|effective|reliable)", "uses absolute wording"),
    (r"perfectly\s+(?:clean|green|safe|effective)", "uses absolute wording"),
    (r"in\s+every\s+(?:situation|case|context)", "claims it holds in every situation"),
    (r"in\s+all\s+cases\b", "claims it holds in all cases"),
    (r"harmless\s+to\s+the\s+environment", "describes it as harmless"),
    (
        r"zero\s+emissions\b(?!\s*(?:from\s+the\s+)?tailpipe)",
        "claims zero emissions without a qualifier",
    ),
]


_NEGATION_CUES = re.compile(
    r"\b(?:not|n't|never|no|none|cannot|without|nor|neither|"
    r"rather\s+than|instead\s+of|far\s+from)\b",
    flags=re.IGNORECASE,
)


def _is_negated(text: str, position: int, window: int = 70) -> bool:
    """True if a negation cue appears shortly before `position` in `text`."""
    return bool(_NEGATION_CUES.search(text[max(0, position - window):position]))


def split_into_claims(summary: str) -> list[str]:
    """Break the summary into individual claims - one per sentence."""
    parts = re.split(r"(?<=[.!?])\s+", summary.strip())
    return [part.strip() for part in parts if len(part.split()) >= 5]


def _parse_json_verdict(raw: str) -> dict | None:
    """Pull the JSON object out of the model reply, tolerating stray text."""
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    status = str(data.get("status", "")).upper().strip()
    if status not in {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}:
        return None
    return {
        "status": status,
        "reason": str(data.get("reason", "")).strip(),
        "evidence": str(data.get("evidence", "")).strip(),
    }


def _locate_evidence(evidence: str, documents: list[dict]) -> str:
    """Find which source file an evidence sentence was taken from."""
    probe = " ".join(evidence.lower().split())[:60]
    if len(probe) < 15:
        return ""
    for doc in documents:
        if probe in " ".join(doc["content"].lower().split()):
            return doc["name"]
    return ""


JUDGE_WORKERS = 4

_VERDICT_CACHE: dict[tuple[str, str], dict] = {}


def _judge_claim(model: str, source_content: str, claim_text: str) -> dict:
    """Rule on one claim, reusing an identical earlier ruling."""
    key = (claim_text, hashlib.sha1(source_content.encode("utf-8")).hexdigest())
    cached = _VERDICT_CACHE.get(key)
    if cached is not None:
        return dict(cached)

    raw = _ask(
        model,
        FACT_CHECK_SYSTEM,
        FACT_CHECK_CLAIM.format(source_content=source_content, claim=claim_text),
        temperature=0.0,
        num_predict=192,
    )
    verdict = _parse_json_verdict(raw) or {
        "status": "PARTIAL",
        "reason": "The verifier did not return a readable verdict for this claim.",
        "evidence": "",
    }
    _VERDICT_CACHE[key] = dict(verdict)
    return verdict


def _build_feedback(results: list[dict], unsupported: list[str]) -> str:
    """Turn the verdicts into the instruction text the summarizer will read."""
    if not unsupported:
        return "All claims in the summary are supported by the source documents."

    blocks = ["The following claims are NOT supported by the sources:", ""]
    for claim in results:
        if claim["status"] == "UNSUPPORTED":
            blocks.append(f'- Claim: "{claim["text"]}"')
            blocks.append(f"  Why it failed: {claim['reason']}")
            if claim["evidence"]:
                blocks.append(f"  The sources actually say: {claim['evidence']}")
            blocks.append("")
    blocks.append("Please revise the summary using only claims supported by the sources.")
    return "\n".join(blocks)




# ---------------------------------------------------------------------------
# RAG indexing
# ---------------------------------------------------------------------------


def index_sources(state: ResearchState) -> dict:
    """Embed the papers into Chroma with nomic-embed-text (once per corpus)."""
    documents = state.get("source_documents", [])
    corpus = memory.corpus_id(documents)
    stats = rag.index_documents(documents, corpus)

    body = (
        f"Embedding model : {memory.EMBED_MODEL}\n"
        f"Vector store    : Chroma ({stats['collection']})\n"
        f"Chunks          : {stats['chunks']} (~{rag.CHUNK_WORDS} words each)\n"
        + (
            "These papers were indexed in an earlier run - existing vectors reused."
            if stats["reused"]
            else "Papers chunked and embedded into a new collection."
        )
    )
    return {
        "corpus_id": corpus,
        "rag_index": stats,
        "trace": _trace(state, "index_sources", "RAG INDEX", "completed", body, stats),
        "node_log": _log(state, "index_sources", "RAG INDEX (Chroma)", "completed"),
    }


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------

AGENTS = ("summarizer", "fact_checker", "guard", "human_review")


def _decide(state: ResearchState) -> tuple[str, str]:
    """The supervisor's routing policy. Pure function of the state."""
    can_retry = state.get("iteration", 0) < state.get("max_iterations", 3)

    if not state.get("summary"):
        return "summarizer", "No summary yet - the summarizer writes the first draft."
    if not state.get("summary_checked"):
        return "fact_checker", "A new draft exists - the fact checker must verify it."
    if not state.get("is_verified"):
        if can_retry:
            return "summarizer", "The fact checker rejected claims - send the feedback back for a rewrite."
        return "finalize", "Claims still unsupported and no correction attempts left."
    if not state.get("guard_checked"):
        return "guard", "Fact check passed - the guard agent runs the final safety checks."
    if not state.get("guard_passed"):
        if can_retry:
            return "summarizer", "The guard blocked the summary - rewrite to fix its issues."
        return "finalize", "The guard blocked the summary and no correction attempts are left."
    if state.get("require_approval") and not state.get("human_decision"):
        return "human_review", "Summary is verified and guarded - ask a human to approve it."
    if state.get("human_decision") == "rejected":
        if can_retry:
            return "summarizer", "The human reviewer asked for changes - rewrite with their notes."
        return "finalize", "The reviewer rejected the summary and no correction attempts are left."
    return "finalize", "All checks passed - finish the run."


def supervisor(state: ResearchState) -> dict:
    """Decide which agent acts next, enforcing the hop limit."""
    hops = state.get("hops", 0)
    max_hops = state.get("max_hops", 12)
    choice, reason = _decide(state)
    hit = False

    if choice != "finalize":
        if hops >= max_hops:
            choice, hit = "finalize", True
            reason = (
                f"Hop limit reached ({hops}/{max_hops}). Stopping safely instead of "
                "handing work to another agent."
            )
        else:
            hops += 1

    log = list(state.get("supervisor_log", []))
    log.append({"hop": hops, "next": choice, "reason": reason})

    body = f"Hop {hops}/{max_hops}\nDecision : -> {choice}\nReason   : {reason}"
    return {
        "next_agent": choice,
        "hops": hops,
        "hop_limit_hit": hit,
        "supervisor_log": log,
        "trace": _trace(
            state, "supervisor", "SUPERVISOR", "error" if hit else "routing", body,
            {"next": choice, "hops": hops},
        ),
        "node_log": _log(
            state, "supervisor", f"SUPERVISOR → {choice}  ·  hop {hops}/{max_hops}",
            "error" if hit else "routing",
        ),
    }


def route_from_supervisor(state: ResearchState) -> str:
    return state.get("next_agent") or "finalize"


# ---------------------------------------------------------------------------
# Agent 1: summarizer
# ---------------------------------------------------------------------------

SUMMARY_QUERIES = [
    "main findings and results",
    "limitations, caveats and conditions",
    "methods, data and study design",
    "conclusions and implications",
    "key numbers and statistics",
]


def _topic(state: ResearchState) -> str:
    documents = state.get("source_documents", [])
    return " ".join(
        (doc.get("content", "").splitlines() or [""])[0].replace("TITLE:", "").strip()
        for doc in documents
    )[:400]


def _thread_notes(state: ResearchState) -> list[str]:
    """Reviewer notes left earlier in this thread (short-term memory)."""
    notes = [
        str(m.content)
        for m in state.get("messages", [])
        if getattr(m, "name", "") == "human_reviewer" and str(m.content).strip()
    ]
    return notes[-3:]


def _memory_block(lessons: list[dict], notes: list[str]) -> str:
    if not lessons and not notes:
        return ""
    lesson_text = ""
    if lessons:
        lesson_text = "Lessons learned in earlier runs (do not repeat these mistakes):\n" + "\n".join(
            f"- {item['lesson']}" for item in lessons
        ) + "\n"
    note_text = ""
    if notes:
        note_text = "Reviewer notes from earlier in this conversation thread:\n" + "\n".join(
            f"- {note}" for note in notes
        ) + "\n"
    return MEMORY_BLOCK.format(lessons=lesson_text, thread_notes=note_text)


def summarizer_agent(state: ResearchState, *, store: BaseStore) -> dict:
    """Writes the summary from retrieved passages, memory and any feedback."""
    iteration = state.get("iteration", 0) + 1
    model = state.get("model", "qwen2.5:3b")
    corpus = state.get("corpus_id", "")
    feedback = state.get("revision_feedback", "")
    is_revision = iteration > 1 and bool(feedback)

    passages = rag.retrieve_many(corpus, SUMMARY_QUERIES, k=4)
    context = rag.format_passages(passages)

    lessons = memory.recall_lessons(store, _topic(state), limit=4)
    notes = _thread_notes(state)
    memory_block = _memory_block(lessons, notes)

    retrievals = list(state.get("retrievals", []))
    retrievals.append(
        {
            "agent": "summarizer",
            "iteration": iteration,
            "query": " | ".join(SUMMARY_QUERIES),
            "hits": passages,
        }
    )

    if is_revision:
        targets = state.get("unsupported_claims") or [feedback[:300]]
        evidence_hits = rag.retrieve_many(corpus, targets, k=3)
        retrievals.append(
            {
                "agent": "summarizer",
                "iteration": iteration,
                "query": "evidence for: " + " | ".join(targets),
                "hits": evidence_hits,
            }
        )
        user_prompt = SUMMARIZER_REVISION.format(
            source_content=context,
            previous_summary=state.get("summary", ""),
            fact_check_feedback=feedback,
            evidence=rag.format_passages(evidence_hits) or "(none)",
            memory_block=memory_block,
        )
        header = "Feedback received. Writing a corrected summary..."
    else:
        user_prompt = SUMMARIZER_FIRST_PASS.format(
            source_content=context, memory_block=memory_block
        )
        header = f"Writing the research summary with {model}..."

    summary = _clean_summary(_ask(model, SUMMARIZER_SYSTEM, user_prompt))

    injected = False
    if state.get("demo_mode", True) and iteration == 1:
        overclaim = build_demo_overclaim(
            state.get("source_documents", []), state.get("source_content", "")
        )
        summary = f"{summary} {overclaim}"
        injected = True

    history = list(state.get("summary_history", []))
    history.append(summary)

    body = (
        f"{header}\n\n"
        f"RAG       : {len(passages)} passages retrieved from Chroma\n"
        f"Memory    : {len(lessons)} long-term lesson(s), {len(notes)} thread note(s)\n\n"
        f'Summary:\n\n"{summary}"'
    )
    if lessons:
        body += "\n\nLessons recalled:\n" + "\n".join(f"  - {l['lesson']}" for l in lessons)
    if injected:
        body += (
            "\n\n[controlled demo mode] One deliberate over-claim was appended to this first "
            "draft so the correction loop is guaranteed to trigger."
        )

    at_iteration = {**state, "iteration": iteration}
    return {
        "summary": summary,
        "summary_history": history,
        "iteration": iteration,
        "recalled_lessons": lessons,
        "retrievals": retrievals,
        "summary_checked": False,
        "is_verified": False,
        "guard_checked": False,
        "guard_passed": False,
        "human_decision": "",
        "messages": [AIMessage(content=summary, name="summarizer")],
        "trace": _trace(
            at_iteration, "summarizer", f"SUMMARIZER AGENT - ITERATION {iteration}",
            "completed", body,
            {"summary": summary, "revision": is_revision, "injected": injected},
        ),
        "node_log": _log(at_iteration, "summarizer", f"SUMMARIZER (iteration {iteration})", "completed"),
    }


# ---------------------------------------------------------------------------
# Agent 2: fact checker
# ---------------------------------------------------------------------------


def _overclaim_reason(text: str) -> str:
    for pattern, description in _OVERCLAIM_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match and not _is_negated(text, match.start()):
            return description
    return ""


def fact_checker_agent(state: ResearchState, *, store: BaseStore) -> dict:
    """Judges each claim against the passages RAG retrieves for that claim."""
    model = state.get("model", "qwen2.5:3b")
    corpus = state.get("corpus_id", "")
    documents = state.get("source_documents", [])

    claims = split_into_claims(state.get("summary", ""))
    hits_per_claim = [rag.retrieve(corpus, claim, k=4) for claim in claims]

    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as pool:
        verdicts = list(
            pool.map(
                lambda pair: _judge_claim(model, rag.format_passages(pair[1]), pair[0]),
                zip(claims, hits_per_claim),
            )
        )

    retrievals = list(state.get("retrievals", []))
    results: list[dict] = []
    unsupported: list[str] = []

    for index, (claim_text, hits, verdict) in enumerate(
        zip(claims, hits_per_claim, verdicts), start=1
    ):
        retrievals.append(
            {
                "agent": "fact_checker",
                "iteration": state.get("iteration", 0),
                "query": claim_text,
                "hits": hits,
            }
        )
        guard_reason = _overclaim_reason(claim_text)
        if guard_reason:
            verdict["status"] = "UNSUPPORTED"
            verdict["reason"] = (
                f"The claim {guard_reason}. The uploaded sources state their "
                "findings with conditions and limits attached, so unconditional "
                "wording asserts more than they support."
            )
            verdict["evidence"] = (
                "State the finding as narrowly as the sources state it, keeping "
                "the conditions and limitations they attach to it."
            )

        source_file = _locate_evidence(verdict["evidence"], documents) or (
            hits[0]["source"] if hits else ""
        )
        results.append(
            {
                "id": index,
                "text": claim_text,
                "status": verdict["status"],
                "reason": verdict["reason"],
                "evidence": verdict["evidence"],
                "source_file": source_file,
            }
        )
        if verdict["status"] == "UNSUPPORTED":
            unsupported.append(claim_text)
            memory.save_lesson(
                store,
                f'Rejected claim: "{claim_text}" - {verdict["reason"]}',
                kind="fact_checker",
                example=claim_text,
            )

    is_verified = bool(results) and not unsupported
    feedback = _build_feedback(results, unsupported)

    claims_history = list(state.get("claims_history", []))
    claims_history.append(results)
    feedback_history = list(state.get("feedback_history", []))
    feedback_history.append(feedback)

    marks = {"SUPPORTED": "OK  ", "PARTIAL": "~   ", "UNSUPPORTED": "XX  "}
    lines = ["Each claim was checked against the top-4 passages Chroma retrieved for it.", ""]
    for claim in results:
        lines.append(f'{marks[claim["status"]]}"{claim["text"]}"')
        lines.append(f"      {claim['status']} - {claim['reason']}")
        if claim["source_file"]:
            lines.append(f"      evidence in {claim['source_file']}")
        lines.append("")
    supported = sum(1 for claim in results if claim["status"] == "SUPPORTED")
    lines.append(f"Claims: {len(results)}   Supported: {supported}   Unsupported: {len(unsupported)}")
    lines.append(
        "VERDICT: SUMMARY VERIFIED"
        if is_verified
        else "VERDICT: UNSUPPORTED CLAIMS - returning to the supervisor"
    )

    status = "completed" if is_verified else "warning"
    return {
        "claims": results,
        "claims_history": claims_history,
        "unsupported_claims": unsupported,
        "fact_check_feedback": feedback,
        "feedback_history": feedback_history,
        "revision_feedback": "" if is_verified else feedback,
        "summary_checked": True,
        "is_verified": is_verified,
        "retrievals": retrievals,
        "messages": [
            AIMessage(
                content=f"{supported}/{len(results)} claims supported."
                + ("" if is_verified else "\n" + feedback),
                name="fact_checker",
            )
        ],
        "trace": _trace(
            state, "fact_checker", "FACT CHECKER AGENT", status, "\n".join(lines),
            {"claims": results, "verified": is_verified},
        ),
        "node_log": _log(state, "fact_checker", "FACT CHECKER", status),
    }


# ---------------------------------------------------------------------------
# Agent 3: guard
# ---------------------------------------------------------------------------

_LEAK_PATTERNS = [
    (r"\bas an ai\b", "talks about itself as an AI"),
    (r"\bi (?:cannot|can't|am unable)\b", "contains a refusal"),
    (r"\b(?:here is|here's) (?:the|a|your)\b", "contains chat preamble"),
    (r"\bthis summary\b|\bthe summary\b", "talks about 'the summary' instead of the research"),
    (r"\bsource_\d+\.(?:txt|pdf)\b|\.pdf\b|\.txt\b", "mentions file names"),
]


def _numbers(text: str) -> list[str]:
    return re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])", text)


def guard_agent(state: ResearchState, *, store: BaseStore) -> dict:
    """Last line of defence: deterministic checks the LLM cannot talk past."""
    summary = state.get("summary", "")
    source_content = state.get("source_content", "")
    issues: list[str] = []

    for sentence in re.split(r"(?<=[.!?])\s+", summary):
        reason = _overclaim_reason(sentence)
        if reason:
            issues.append(f'Absolute wording: "{sentence.strip()}" ({reason}).')

    source_numbers = set(_numbers(source_content))
    for number in dict.fromkeys(_numbers(summary)):
        if number not in source_numbers:
            issues.append(f'The number "{number}" does not appear in any uploaded paper.')

    lowered = summary.lower()
    for pattern, description in _LEAK_PATTERNS:
        if re.search(pattern, lowered):
            issues.append(f"Formatting: the text {description}.")

    sentences = [s for s in re.split(r"(?<=[.!?])\s+", summary.strip()) if s]
    if not 2 <= len(sentences) <= 8:
        issues.append(f"Length: {len(sentences)} sentences (expected 4-6).")

    passed = not issues
    for issue in issues:
        memory.save_lesson(store, f"Guard blocked: {issue}", kind="guard")

    feedback = (
        ""
        if passed
        else "The guard agent blocked the summary:\n"
        + "\n".join(f"- {i}" for i in issues)
        + "\nFix every issue. Use only numbers that appear in the sources."
    )
    body = (
        "Checks: absolute wording, numbers present in sources, prompt leakage, length.\n\n"
        + ("All guard checks passed." if passed else feedback)
    )
    status = "completed" if passed else "warning"
    return {
        "guard_checked": True,
        "guard_passed": passed,
        "guard_issues": issues,
        "revision_feedback": feedback or state.get("revision_feedback", ""),
        "messages": [AIMessage(content=body, name="guard")],
        "trace": _trace(state, "guard", "GUARD AGENT", status, body, {"issues": issues}),
        "node_log": _log(state, "guard", "GUARD", status),
    }


# ---------------------------------------------------------------------------
# Human approval (pauses the graph with interrupt)
# ---------------------------------------------------------------------------


def human_review(state: ResearchState, *, store: BaseStore) -> dict:
    """Pause the run until a person approves or rejects the summary.

    interrupt() saves the state to the SQLite checkpointer and stops. The UI
    resumes the same thread with Command(resume={"approved": ..., "feedback": ...}).
    """
    decision = interrupt(
        {
            "summary": state.get("summary", ""),
            "iteration": state.get("iteration", 0),
            "claims": state.get("claims", []),
            "question": "Approve this summary, or request changes?",
        }
    ) or {}

    approved = bool(decision.get("approved"))
    feedback = str(decision.get("feedback", "")).strip()
    if not approved and not feedback:
        feedback = "The reviewer rejected the summary. Make it more precise and closer to the sources."

    if not approved:
        memory.save_lesson(store, f"Reviewer asked: {feedback}", kind="human_reviewer")

    note = ("APPROVED" if approved else "CHANGES REQUESTED") + (f" - {feedback}" if feedback else "")
    status = "completed" if approved else "warning"
    return {
        "human_decision": "approved" if approved else "rejected",
        "human_feedback": feedback,
        "revision_feedback": (
            state.get("revision_feedback", "")
            if approved
            else f"The human reviewer requested changes:\n{feedback}"
        ),
        "messages": [HumanMessage(content=feedback or "Approved.", name="human_reviewer")],
        "trace": _trace(state, "human_review", "HUMAN APPROVAL", status, f"Reviewer decision: {note}"),
        "node_log": _log(
            state, "human_review",
            "HUMAN APPROVAL · approved" if approved else "HUMAN APPROVAL · changes requested",
            status,
        ),
    }


# ---------------------------------------------------------------------------
# Finalize
# ---------------------------------------------------------------------------


def final_status(state: ResearchState) -> str:
    if state.get("hop_limit_hit"):
        return "HOP LIMIT REACHED"
    if not state.get("is_verified"):
        return "UNVERIFIED"
    if not state.get("guard_passed"):
        return "BLOCKED BY GUARD"
    if state.get("require_approval"):
        return "APPROVED" if state.get("human_decision") == "approved" else "REJECTED BY REVIEWER"
    return "VERIFIED"


def finalize(state: ResearchState, *, store: BaseStore) -> dict:
    """Terminal node: decide the outcome and save it to long-term memory."""
    status = final_status(state)
    ok = status in {"APPROVED", "VERIFIED"}
    corpus = state.get("corpus_id", "")

    if ok and corpus:
        memory.save_summary(store, corpus, state.get("thread_id", ""), state.get("summary", ""), status)

    body = (
        f"Final status : {status}\n"
        f"Iterations   : {state.get('iteration', 0)}/{state.get('max_iterations', 3)}\n"
        f"Supervisor   : {state.get('hops', 0)}/{state.get('max_hops', 12)} hops\n"
        + (
            "Summary saved to long-term memory (SQLite store).\n"
            if ok
            else "Summary NOT saved to long-term memory.\n"
        )
        + "Routing to END."
    )
    return {
        "final_status": status,
        "messages": [AIMessage(content=f"Run finished: {status}.", name="supervisor")],
        "trace": _trace(state, "finalize", "END", "completed" if ok else "error", body),
        "node_log": _log(state, "finalize", status, "completed" if ok else "error"),
    }
