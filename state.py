from __future__ import annotations

from typing import Any, Literal, TypedDict


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
    """The LangGraph state object."""

    sources: list[str]
    source_documents: list[dict]
    source_content: str

    summary: str
    summary_history: list[str]

    claims: list[Claim]
    claims_history: list[list]
    unsupported_claims: list[str]
    fact_check_feedback: str
    feedback_history: list[str]

    iteration: int
    max_iterations: int
    is_verified: bool

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
) -> ResearchState:
    """Create the state the graph starts from. Nothing is loaded yet."""
    return ResearchState(
        sources=[],
        source_documents=[],
        source_content="",
        summary="",
        summary_history=[],
        claims=[],
        claims_history=[],
        unsupported_claims=[],
        fact_check_feedback="",
        feedback_history=[],
        iteration=0,
        max_iterations=max_iterations,
        is_verified=False,
        demo_mode=demo_mode,
        model=model,
        trace=[],
        node_log=[],
        sources_dir=sources_dir,
        selected_sources=list(selected_sources or []),
    )
