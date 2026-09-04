from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from nodes import fact_check, finalize, read_source, route_after_fact_check, summarize
from state import ResearchState, build_initial_state


def build_graph():
    """Build and compile the research summarizer graph."""
    graph = StateGraph(ResearchState)

    graph.add_node("read_source", read_source)
    graph.add_node("summarize", summarize)
    graph.add_node("fact_check", fact_check)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "read_source")
    graph.add_edge("read_source", "summarize")
    graph.add_edge("summarize", "fact_check")

    graph.add_conditional_edges(
        "fact_check",
        route_after_fact_check,
        {
            "summarize": "summarize",
            "finish": "finalize",
        },
    )

    graph.add_edge("finalize", END)

    return graph.compile()


def run_workflow(
    sources_dir: str,
    model: str = "qwen2.5:3b",
    max_iterations: int = 3,
    demo_mode: bool = True,
    selected_sources: list[str] | None = None,
    on_event=None,
) -> ResearchState:
    """Run the graph end to end."""
    app = build_graph()
    state = build_initial_state(
        sources_dir=sources_dir,
        model=model,
        max_iterations=max_iterations,
        demo_mode=demo_mode,
        selected_sources=selected_sources,
    )

    final_state: ResearchState = dict(state)  # type: ignore[assignment]

    config = {"recursion_limit": max_iterations * 3 + 6}

    for chunk in app.stream(state, config=config):
        for node_name, update in chunk.items():
            if update:
                final_state.update(update)
            if on_event is not None:
                on_event(node_name, dict(final_state))

    return final_state


if __name__ == "__main__":
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    result = run_workflow(sources_dir=os.path.join(here, "sources"))

    print("\n" + "=" * 70)
    print("FINAL STATE")
    print("=" * 70)
    print("iterations :", result.get("iteration"))
    print("verified   :", result.get("is_verified"))
    print("\nFINAL SUMMARY:\n", result.get("summary"))
