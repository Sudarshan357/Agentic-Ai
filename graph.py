"""The supervisor graph.

    START -> read_source -> index_sources -> supervisor
    supervisor -> summarizer | fact_checker | guard | human_review | finalize
    every agent -> supervisor            (the supervisor decides again)
    finalize -> END

The supervisor counts its hand-offs and stops at max_hops. human_review pauses
the run with interrupt(); the thread is saved by the SQLite checkpointer and
resumed with Command(resume=...).
"""

from __future__ import annotations

import threading
import uuid

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

import memory
from nodes import (
    fact_checker_agent,
    finalize,
    guard_agent,
    human_review,
    index_sources,
    read_source,
    route_from_supervisor,
    summarizer_agent,
    supervisor,
)
from state import ResearchState, build_initial_state

AGENT_NODES = ("summarizer", "fact_checker", "guard", "human_review")


def build_graph(checkpointer=None, store=None):
    """Build and compile the multi-agent research graph."""
    graph = StateGraph(ResearchState)

    graph.add_node("read_source", read_source)
    graph.add_node("index_sources", index_sources)
    graph.add_node("supervisor", supervisor)
    graph.add_node("summarizer", summarizer_agent)
    graph.add_node("fact_checker", fact_checker_agent)
    graph.add_node("guard", guard_agent)
    graph.add_node("human_review", human_review)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "read_source")
    graph.add_edge("read_source", "index_sources")
    graph.add_edge("index_sources", "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {name: name for name in (*AGENT_NODES, "finalize")},
    )
    for name in AGENT_NODES:
        graph.add_edge(name, "supervisor")

    graph.add_edge("finalize", END)

    return graph.compile(
        checkpointer=checkpointer or memory.get_checkpointer(),
        store=store or memory.get_store(),
    )


_graph = None
_graph_lock = threading.Lock()


def get_graph():
    global _graph
    with _graph_lock:
        if _graph is None:
            _graph = build_graph()
        return _graph


def new_thread_id() -> str:
    return f"thread-{uuid.uuid4().hex[:8]}"


def _drive(graph_input, thread_id: str, max_hops: int, on_event=None) -> dict:
    """Stream the graph until it ends or pauses; return the latest state."""
    app = get_graph()
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 2 * max_hops + 12,
    }

    # "updates" says which node just ran; the "values" chunk that follows it
    # is the full state after that node.
    finished: list[str] = []
    for mode, chunk in app.stream(
        graph_input, config=config, stream_mode=["updates", "values"]
    ):
        if mode == "updates":
            finished.extend(name for name in chunk if not name.startswith("__"))
        elif finished and on_event is not None:
            for node_name in finished:
                on_event(node_name, dict(chunk))
            finished.clear()

    snapshot = app.get_state(config)
    values = dict(snapshot.values)
    values["thread_id"] = thread_id
    values["awaiting_approval"] = snapshot.interrupts[0].value if snapshot.interrupts else None
    return values


def run_workflow(
    sources_dir: str,
    model: str = "qwen2.5:3b",
    max_iterations: int = 3,
    demo_mode: bool = True,
    selected_sources: list[str] | None = None,
    on_event=None,
    max_hops: int = 12,
    require_approval: bool = True,
    thread_id: str | None = None,
) -> dict:
    """Start a run on `thread_id` (a new thread if none is given).

    If human approval is on, the returned state has `awaiting_approval` set and
    the run must be continued with resume_workflow().
    """
    thread_id = thread_id or new_thread_id()
    state = build_initial_state(
        sources_dir=sources_dir,
        model=model,
        max_iterations=max_iterations,
        demo_mode=demo_mode,
        selected_sources=selected_sources,
        max_hops=max_hops,
        require_approval=require_approval,
        thread_id=thread_id,
    )
    files = ", ".join(selected_sources or []) or "the uploaded papers"
    state["messages"] = [
        HumanMessage(content=f"Summarize and verify: {files}", name="user")
    ]
    return _drive(state, thread_id, max_hops, on_event)


def resume_workflow(
    thread_id: str,
    approved: bool,
    feedback: str = "",
    on_event=None,
) -> dict:
    """Answer the human-approval question and let the run continue."""
    current = get_graph().get_state({"configurable": {"thread_id": thread_id}}).values
    return _drive(
        Command(resume={"approved": approved, "feedback": feedback}),
        thread_id,
        current.get("max_hops", 12),
        on_event,
    )


def thread_messages(thread_id: str) -> list:
    """The full conversation stored for a thread (short-term memory)."""
    if not thread_id:
        return []
    state = get_graph().get_state({"configurable": {"thread_id": thread_id}})
    return list(state.values.get("messages", [])) if state and state.values else []


if __name__ == "__main__":
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    result = run_workflow(sources_dir=os.path.join(here, "sources"), require_approval=False)
    print("status     :", result.get("final_status"))
    print("iterations :", result.get("iteration"))
    print("hops       :", result.get("hops"))
    print("\nFINAL SUMMARY:\n", result.get("summary"))
