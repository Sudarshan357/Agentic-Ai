from __future__ import annotations

import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # pragma: no cover - non-Windows terminals
    pass

import nodes
from graph import run_workflow

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


def test_full_workflow() -> int:
    """Run the graph for real and check the demonstration story holds."""
    started = time.time()

    def on_event(node_name: str, state: dict) -> None:
        print(f"  -> node finished: {node_name:<12} (iteration {state.get('iteration', 0)})")

    result = run_workflow(
        sources_dir=os.path.join(HERE, "sources"),
        model="qwen2.5:3b",
        max_iterations=3,
        demo_mode=True,
        on_event=on_event,
    )
    elapsed = time.time() - started

    print("\n" + BAR)
    print("EXECUTION TRACE")
    print(BAR)
    for event in result["trace"]:
        print(f"\n[{event['step']}] {event['title']}   ({event['status']})")
        print("-" * 72)
        print(event["body"])
        print()
        print(" " * 34 + "|")
        print(" " * 34 + "v")

    print("\n" + BAR)
    print("ASSERTIONS")
    print(BAR)

    history = result.get("summary_history", [])
    claims_history = result.get("claims_history", [])
    checks: list[tuple[str, bool]] = [
        ("1. sources were read", len(result.get("sources", [])) == 3),
        ("2. a summary was generated", bool(history)),
        (
            "3. iteration 1 contains an unsupported over-claim",
            bool(claims_history)
            and any(c["status"] == "UNSUPPORTED" for c in claims_history[0]),
        ),
        (
            "4. the fact checker produced claim-level verdicts",
            bool(claims_history) and len(claims_history[0]) >= 3,
        ),
        ("5. conditional routing looped back", len(history) >= 2),
        (
            "6. the summarizer received feedback",
            bool(result.get("feedback_history"))
            and "not supported" in result["feedback_history"][0].lower(),
        ),
        (
            "7. the corrected summary makes no unnegated over-claim",
            len(history) >= 2
            and not any(
                guard_flags(sentence)
                for sentence in nodes.split_into_claims(history[-1])
            ),
        ),
        ("8. the final fact check passed", result.get("is_verified") is True),
        (
            "9. the graph stayed within max_iterations",
            result.get("iteration", 99) <= result.get("max_iterations", 3),
        ),
        (
            "10. the trace is complete",
            len(result.get("trace", [])) >= 5 and result["trace"][-1]["title"] == "END",
        ),
    ]

    failed = 0
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}]  {label}")
        failed += not passed

    print("\n" + BAR)
    print(f"iterations : {result.get('iteration')}")
    print(f"verified   : {result.get('is_verified')}")
    print(f"runtime    : {elapsed:.1f}s")
    print(BAR)

    print("\nITERATION 1 SUMMARY (rejected):\n")
    print(history[0] if history else "(none)")
    if len(history) > 1:
        print("\nFINAL SUMMARY (verified):\n")
        print(history[-1])

    return failed


def main() -> int:
    print(BAR)
    print("MULTI-STEP RESEARCH SUMMARIZER - WORKFLOW TEST")
    print(BAR)

    print("\nPART 1: over-claim guard (no model needed)")
    failed = test_overclaim_guard()

    print("\nPART 2: source selection (no model needed)")
    failed += test_source_selection()

    print("\nPART 3: full graph run against Ollama")
    failed += test_full_workflow()

    print(f"\n{'ALL CHECKS PASSED' if not failed else f'{failed} CHECK(S) FAILED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
