from __future__ import annotations

import hashlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import json
import os
import re
from typing import Any

from langchain_ollama import ChatOllama

from prompts import (
    FACT_CHECK_CLAIM,
    FACT_CHECK_SYSTEM,
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


def summarize(state: ResearchState) -> dict:
    """Iteration 1 summarizes from scratch; later ones rewrite from the feedback."""
    iteration = state.get("iteration", 0) + 1
    model = state.get("model", "qwen2.5:3b")
    feedback = state.get("fact_check_feedback", "")
    is_revision = iteration > 1 and bool(feedback)

    if is_revision:
        user_prompt = SUMMARIZER_REVISION.format(
            source_content=state["source_content"],
            previous_summary=state.get("summary", ""),
            fact_check_feedback=feedback,
        )
        header = "Previous fact-check feedback received. Generating corrected summary..."
    else:
        user_prompt = SUMMARIZER_FIRST_PASS.format(
            source_content=state["source_content"]
        )
        header = f"Generating research summary using {model}..."

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

    body = f'{header}\n\nSummary generated:\n\n"{summary}"'
    if injected:
        body += (
            "\n\n[controlled demo mode] One deliberate over-claim was appended to this first "
            "draft so the fact-check loop is guaranteed to trigger. No injection "
            "happens on later iterations."
        )

    state_at_iteration = {**state, "iteration": iteration}

    return {
        "summary": summary,
        "summary_history": history,
        "iteration": iteration,
        "trace": _trace(
            state_at_iteration,
            "summarize",
            f"SUMMARIZE NODE - ITERATION {iteration}",
            "completed",
            body,
            {"summary": summary, "revision": is_revision, "injected": injected},
        ),
        "node_log": _log(
            state_at_iteration,
            "summarize",
            f"SUMMARIZE (iteration {iteration})",
            "completed",
        ),
    }


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


def fact_check(state: ResearchState) -> dict:
    """Judge every claim against the sources: LLM verdict plus a deterministic guard."""
    model = state.get("model", "qwen2.5:3b")
    summary = state.get("summary", "")
    source_content = state.get("source_content", "")
    documents = state.get("source_documents", [])

    claims = split_into_claims(summary)
    results: list[dict] = []
    unsupported: list[str] = []

    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as pool:
        verdicts = list(
            pool.map(lambda c: _judge_claim(model, source_content, c), claims)
        )

    for index, (claim_text, verdict) in enumerate(zip(claims, verdicts), start=1):
        guard_reason = ""
        for pattern, description in _OVERCLAIM_PATTERNS:
            match = re.search(pattern, claim_text, flags=re.IGNORECASE)
            if match and not _is_negated(claim_text, match.start()):
                guard_reason = description
                break

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

        results.append(
            {
                "id": index,
                "text": claim_text,
                "status": verdict["status"],
                "reason": verdict["reason"],
                "evidence": verdict["evidence"],
                "source_file": _locate_evidence(verdict["evidence"], documents),
            }
        )

        if verdict["status"] == "UNSUPPORTED":
            unsupported.append(claim_text)

    is_verified = len(unsupported) == 0 and len(results) > 0
    feedback = _build_feedback(results, unsupported)

    claims_history = list(state.get("claims_history", []))
    claims_history.append(results)

    feedback_history = list(state.get("feedback_history", []))
    feedback_history.append(feedback)

    marks = {"SUPPORTED": "OK  ", "PARTIAL": "~   ", "UNSUPPORTED": "XX  "}
    lines = ["Analyzing generated claims against source documents...", ""]
    for claim in results:
        lines.append(f'{marks[claim["status"]]}"{claim["text"]}"')
        lines.append(f"      {claim['status']} - {claim['reason']}")
        if claim["source_file"]:
            lines.append(f"      evidence located in {claim['source_file']}")
        lines.append("")

    supported_count = sum(1 for claim in results if claim["status"] == "SUPPORTED")
    lines.append(f"Claims analysed: {len(results)}")
    lines.append(f"Supported: {supported_count}    Unsupported: {len(unsupported)}")
    lines.append("")
    lines.append(
        "FINAL DECISION: SUMMARY VERIFIED"
        if is_verified
        else "FINAL DECISION: UNSUPPORTED CLAIM DETECTED - correction required"
    )

    return {
        "claims": results,
        "claims_history": claims_history,
        "unsupported_claims": unsupported,
        "fact_check_feedback": feedback,
        "feedback_history": feedback_history,
        "is_verified": is_verified,
        "trace": _trace(
            state,
            "fact_check",
            "FACT CHECK NODE",
            "completed" if is_verified else "warning",
            "\n".join(lines),
            {"claims": results, "verified": is_verified},
        ),
        "node_log": _log(
            state, "fact_check", "FACT CHECK", "completed" if is_verified else "warning"
        ),
    }


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


def route_after_fact_check(state: ResearchState) -> str:
    """Return "summarize" to loop back, "finish" to stop."""
    if state.get("is_verified"):
        return "finish"
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "finish"
    return "summarize"


def finalize(state: ResearchState) -> dict:
    """Terminal node: writes the closing trace entry."""
    verified = state.get("is_verified", False)
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if verified:
        plural = "s" if iteration != 1 else ""
        body = (
            f"All claims supported after {iteration} iteration{plural}.\n\n"
            "FINAL DECISION: SUMMARY VERIFIED\nRouting to END."
        )
        return {
            "trace": _trace(state, "finalize", "END", "completed", body),
            "node_log": _log(state, "finalize", "VERIFIED", "completed"),
        }

    remaining = len(state.get("unsupported_claims", []))
    body = (
        f"Maximum correction attempts reached ({max_iterations}).\n"
        f"{remaining} claim(s) remain unsupported.\n\n"
        "FINAL DECISION: VERIFICATION FAILED - stopping safely to avoid an "
        "infinite loop.\nRouting to END."
    )
    return {
        "trace": _trace(state, "finalize", "END", "error", body),
        "node_log": _log(state, "finalize", "VERIFICATION FAILED", "error"),
    }
