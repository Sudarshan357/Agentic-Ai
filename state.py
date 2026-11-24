from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class Claim(TypedDict):
    """One atomic claim extracted from the generated summary."""

    id: int
    text: str
    status: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED"]
    reason: str
    evidence: str
    source_file: str


class TraceEvent(TypedDict):
    """One entry in the human-readable execution trace shown in the UI."""

    step: int
    node: str
    title: str
    status: str
    iteration: int
    body: str
    payload: dict[str, Any]


class ResearchState(TypedDict, total=False):
    """The LangGraph state object.

    Every field except `messages` is reset at the start of a run. `messages`
    uses the add_messages reducer, so it keeps growing across runs on the same
    thread: that is the short-term (thread) memory the agents read from.
    """

    # --- thread memory (persists across runs on one thread) ---
    messages: Annotated[list[AnyMessage], add_messages]
    thread_id: str

    # --- sources and RAG ---
    sources: list[str]
    source_documents: list[dict]
    source_content: str
    corpus_id: str
    rag_index: dict
    retrievals: list[dict]

    # --- summarizer agent ---
    summary: str
    summary_history: list[str]
    recalled_lessons: list[dict]

    # --- fact checker agent ---
    claims: list[Claim]
    claims_history: list[list]
    unsupported_claims: list[str]
    fact_check_feedback: str
    feedback_history: list[str]
    summary_checked: bool
    is_verified: bool

    # --- guard agent ---
    guard_checked: bool
    guard_passed: bool
    guard_issues: list[str]

    # --- human approval ---
    require_approval: bool
    human_decision: str  # "" | "approved" | "rejected"
    human_feedback: str

    # --- supervisor ---
    next_agent: str
    hops: int
    max_hops: int
    hop_limit_hit: bool
    supervisor_log: list[dict]
    revision_feedback: str

    # --- loop control / config ---
    iteration: int
    max_iterations: int
    final_status: str

    sources_dir: str
    selected_sources: list[str]
    demo_mode: bool
    model: str

    trace: list[TraceEvent]
    node_log: list[dict]


def build_initial_state(
    sources_dir: str,
    model: str = "qwen2.5:3b",
    max_iterations: int = 3,
    demo_mode: bool = True,
    selected_sources: list[str] | None = None,
    max_hops: int = 12,
    require_approval: bool = True,
    thread_id: str = "",
) -> ResearchState:
    """Create the state a run starts from. Nothing is loaded yet."""
    return ResearchState(
        thread_id=thread_id,
        sources=[],
        source_documents=[],
        source_content="",
        corpus_id="",
        rag_index={},
        retrievals=[],
        summary="",
        summary_history=[],
        recalled_lessons=[],
        claims=[],
        claims_history=[],
        unsupported_claims=[],
        fact_check_feedback="",
        feedback_history=[],
        summary_checked=False,
        is_verified=False,
        guard_checked=False,
        guard_passed=False,
        guard_issues=[],
        require_approval=require_approval,
        human_decision="",
        human_feedback="",
        next_agent="",
        hops=0,
        max_hops=max_hops,
        hop_limit_hit=False,
        supervisor_log=[],
        revision_feedback="",
        iteration=0,
        max_iterations=max_iterations,
        final_status="",
        demo_mode=demo_mode,
        model=model,
        trace=[],
        node_log=[],
        sources_dir=sources_dir,
        selected_sources=list(selected_sources or []),
    )
