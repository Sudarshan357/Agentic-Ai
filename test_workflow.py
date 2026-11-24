from __future__ import annotations

import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # pragma: no cover - non-Windows terminals
    pass

import tempfile

# Keep test runs out of the real memory folder.
os.environ.setdefault("RESEARCH_MEMORY_DIR", tempfile.mkdtemp(prefix="research_mem_test_"))

import memory
import nodes
from graph import resume_workflow, run_workflow, thread_messages

HERE = os.path.dirname(os.path.abspath(__file__))

BAR = "=" * 72


def guard_flags(claim: str) -> str:
    """Reproduce the guard decision the fact_check node makes for one claim."""
    for pattern, description in nodes._OVERCLAIM_PATTERNS:
        match = re.search(pattern, claim, flags=re.IGNORECASE)
        if match and not nodes._is_negated(claim, match.start()):
            return description
    return ""


def test_overclaim_guard() -> int:
    """The guard must catch absolute wording but ignore NEGATED wording."""
    cases = [
        ("Overall, electric vehicles have zero environmental impact.", True),
        ("EVs are completely clean from production to disposal.", True),
        ("Electric vehicles have no environmental impact whatsoever.", True),
        ("Electric vehicles have zero emissions.", True),
        ("Electric vehicles do not have zero emissions overall.", False),
        ("EVs should not be described as having zero environmental impact.", False),
        ("EVs are not completely clean, because battery production has impacts.", False),
        ("Electric vehicles produce zero tailpipe emissions.", False),
        ("Their benefits depend on the electricity mix and battery manufacturing.", False),
    ]

    failed = 0
    for claim, should_flag in cases:
        flagged = bool(guard_flags(claim))
        passed = flagged == should_flag
        failed += not passed
        verdict = "flagged" if flagged else "allowed"
        print(f"  [{'PASS' if passed else 'FAIL'}]  {verdict:<8} {claim[:58]}")
    return failed


def test_source_selection() -> int:
    """read_source must honour the Step 1 source checkboxes."""
    from nodes import read_source

    sources_dir = os.path.join(HERE, "sources")
    failed = 0
    for selection, expected in [
        ([], 3),
        (["source_1.txt"], 1),
        (["source_1.txt", "source_3.txt"], 2),
    ]:
        state = {"sources_dir": sources_dir, "selected_sources": selection}
        loaded = read_source(state).get("sources", [])
        ok = len(loaded) == expected and (not selection or loaded == selection)
        failed += not ok
        label = selection or "all"
        print(f"  [{'PASS' if ok else 'FAIL'}]  selection {label} -> {loaded}")
    return failed


def test_supervisor_policy() -> int:
    """Routing decisions and the hop limit, without any model."""
    base = {"max_hops": 5, "hops": 0, "iteration": 0, "max_iterations": 3,
            "require_approval": True}
    cases = [
        ("no summary -> summarizer", {}, "summarizer"),
        ("new draft -> fact_checker", {"summary": "x", "iteration": 1}, "fact_checker"),
        ("rejected -> summarizer",
         {"summary": "x", "iteration": 1, "summary_checked": True}, "summarizer"),
        ("rejected, no retries -> finalize",
         {"summary": "x", "iteration": 3, "summary_checked": True}, "finalize"),
        ("verified -> guard",
         {"summary": "x", "iteration": 1, "summary_checked": True, "is_verified": True}, "guard"),
        ("guarded -> human_review",
         {"summary": "x", "iteration": 1, "summary_checked": True, "is_verified": True,
          "guard_checked": True, "guard_passed": True}, "human_review"),
        ("approved -> finalize",
         {"summary": "x", "iteration": 1, "summary_checked": True, "is_verified": True,
          "guard_checked": True, "guard_passed": True, "human_decision": "approved"}, "finalize"),
        ("hop limit -> finalize", {"hops": 5}, "finalize"),
    ]
    failed = 0
    for label, extra, expected in cases:
        update = nodes.supervisor({**base, **extra})
        ok = update["next_agent"] == expected
        if label.startswith("hop limit"):
            ok = ok and update["hop_limit_hit"] is True
        failed += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label:<34} got {update['next_agent']}")
    return failed


def test_full_workflow() -> int:
    """Run the graph for real: pause for approval, reject once, then approve."""
    started = time.time()
    seen: list[str] = []

    def on_event(node_name: str, state: dict) -> None:
        seen.append(node_name)
        extra = f"-> {state.get('next_agent')}" if node_name == "supervisor" else ""
        print(f"  . {node_name:<13} hop {state.get('hops', 0):<3} {extra}")

    result = run_workflow(
        sources_dir=os.path.join(HERE, "sources"),
        model="qwen2.5:3b",
        max_iterations=3,
        demo_mode=True,
        max_hops=14,
        require_approval=True,
        on_event=on_event,
    )
    thread_id = result["thread_id"]
    paused = bool(result.get("awaiting_approval"))
    first_pause_iteration = result.get("iteration", 0)
    print(f"\n  paused for approval: {paused} (iteration {first_pause_iteration})")

    result = resume_workflow(
        thread_id, approved=False,
        feedback="Mention that the benefit depends on the electricity mix.",
        on_event=on_event,
    )
    rewrote_after_rejection = result.get("iteration", 0) > first_pause_iteration
    if result.get("awaiting_approval"):
        result = resume_workflow(thread_id, approved=True, on_event=on_event)
    elapsed = time.time() - started

    print("\n" + BAR)
    print("EXECUTION TRACE")
    print(BAR)
    for event in result["trace"]:
        print(f"\n[{event['step']}] {event['title']}   ({event['status']})")
        print("-" * 72)
        print(event["body"])

    print("\n" + BAR)
    print("ASSERTIONS")
    print(BAR)

    history = result.get("summary_history", [])
    claims_history = result.get("claims_history", [])
    messages = thread_messages(thread_id)
    lessons = memory.all_lessons(memory.get_store())
    agents = {"summarizer", "fact_checker", "guard"}
    checks: list[tuple[str, bool]] = [
        ("1. sources were read and indexed into Chroma",
         len(result.get("sources", [])) == 3 and result.get("rag_index", {}).get("chunks", 0) > 0),
        ("2. all three agents ran", agents <= set(seen)),
        ("3. the supervisor routed between them", seen.count("supervisor") >= 5),
        ("4. iteration 1 contained an unsupported over-claim",
         bool(claims_history) and any(c["status"] == "UNSUPPORTED" for c in claims_history[0])),
        ("5. the fact checker used RAG per claim",
         any(r["agent"] == "fact_checker" and r["hits"] for r in result.get("retrievals", []))),
        ("6. the graph paused for human approval", paused),
        ("7. a rejection sent work back to the summarizer", rewrote_after_rejection),
        ("8. the corrected summary makes no unnegated over-claim",
         not any(guard_flags(s) for s in nodes.split_into_claims(history[-1] if history else ""))),
        ("9. the run finished APPROVED", result.get("final_status") == "APPROVED"),
        ("10. hops stayed within the hop limit", result.get("hops", 99) <= result.get("max_hops", 0)),
        ("11. thread memory kept the reviewer note",
         any(getattr(m, "name", "") == "human_reviewer" for m in messages)),
        ("12. long-term memory stored lessons", len(lessons) >= 1),
        ("13. the trace ends at END", result["trace"][-1]["title"] == "END"),
    ]

    failed = 0
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}]  {label}")
        failed += not passed

    print("\n" + BAR)
    print(f"final status : {result.get('final_status')}")
    print(f"iterations   : {result.get('iteration')}")
    print(f"hops         : {result.get('hops')}/{result.get('max_hops')}")
    print(f"runtime      : {elapsed:.1f}s")
    print(BAR)
    print("\nFINAL SUMMARY:\n")
    print(history[-1] if history else "(none)")
    return failed


def main() -> int:
    print(BAR)
    print("MULTI-STEP RESEARCH SUMMARIZER - WORKFLOW TEST")
    print(BAR)

    print("\nPART 1: over-claim guard (no model needed)")
    failed = test_overclaim_guard()

    print("\nPART 2: source selection (no model needed)")
    failed += test_source_selection()

    print("\nPART 3: supervisor routing and hop limit (no model needed)")
    failed += test_supervisor_policy()

    print("\nPART 4: full graph run against Ollama")
    failed += test_full_workflow()

    print(f"\n{'ALL CHECKS PASSED' if not failed else f'{failed} CHECK(S) FAILED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
