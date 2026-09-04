from __future__ import annotations

import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):  # pragma: no cover
    pass

from streamlit.testing.v1 import AppTest

BAR = "=" * 72


def session_get(app, key):
    """AppTest session_state proxy has no .get(), so read it defensively."""
    try:
        return app.session_state[key]
    except (KeyError, AttributeError):
        return None


def report(stage: str, app: AppTest) -> int:
    """Print any exception the Streamlit script raised. Returns a failure count."""
    if app.exception:
        print(f"  [FAIL] {stage}: {len(app.exception)} exception(s)")
        for exception in app.exception:
            print("        " + str(exception.value).replace("\n", "\n        "))
        return len(app.exception)
    print(f"  [PASS] {stage}: no exceptions")
    return 0


def main() -> int:
    failures = 0

    print(BAR)
    print("STREAMLIT UI TEST")
    print(BAR)

    print("\n1. Initial render (no run yet)")
    app = AppTest.from_file("app.py", default_timeout=120)
    app.run()
    failures += report("initial render", app)

    print(f"  tabs rendered      : {len(app.tabs)}")
    print(f"  buttons            : {[b.label.strip() for b in app.button]}")
    print(f"  checkboxes         : {[c.label for c in app.checkbox]}")
    print(f"  sliders            : {[s.label for s in app.slider]}")
    print(f"  selectboxes        : {[s.label for s in app.selectbox]}")
    print(f"  text inputs        : {[i.label for i in app.text_input]}")

    topic_inputs = [i for i in app.text_input if "topic" in i.label.lower()]
    for ok, label in [
        (not topic_inputs, "no research topic input anywhere"),
        (
            any("Upload research sources" in m.value for m in app.markdown),
            "Upload research sources panel rendered",
        ),
        (
            any("RUN RESEARCH" in b.label for b in app.button),
            "primary Run Research button",
        ),
        (
            any(c.label == "Guarantee the correction loop" for c in app.checkbox),
            "Controlled Demo Mode toggle",
        ),
    ]:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        failures += not ok

    idle_markup = " ".join(block.value for block in app.markdown)
    for stage, _key in __import__("ui").JOURNEY:
        ok = stage in idle_markup
        print(f"  [{'PASS' if ok else 'FAIL'}] journey stage: {stage}")
        failures += not ok

    if len(app.tabs) < 5:
        print(f"  [FAIL] expected 5 tabs, found {len(app.tabs)}")
        failures += 1
    else:
        print("  [PASS] all five tabs present")

    if not app.button:
        print("  [FAIL] the RUN button was not rendered")
        return failures + 1

    demo_toggles = [c for c in app.checkbox if c.label == "Guarantee the correction loop"]
    demo_default = demo_toggles[0].value if demo_toggles else None
    print(f"  demo mode default  : {demo_default}")
    if demo_default is not True:
        print("  [FAIL] 'Demonstrate correction loop' should default to ON")
        failures += 1
    else:
        print("  [PASS] demo mode defaults to ON")

    print("\n2. Run button gating (no files uploaded yet)")
    run_button = next(b for b in app.button if "RUN RESEARCH" in b.label)
    gated = bool(run_button.disabled)
    print(f"  [{'PASS' if gated else 'FAIL'}] Run Research disabled until papers are uploaded")
    if not gated:
        failures += 1

    uploaders = getattr(app, "file_uploader", [])
    has_uploader = len(uploaders) > 0
    print(f"  [{'PASS' if has_uploader else 'FAIL'}] file uploader rendered")
    if not has_uploader:
        failures += 1

    print("\n" + "=" * 70)
    print("UI CHECKS COMPLETE" if not failures else f"{failures} UI CHECK(S) FAILED")
    print("=" * 70)
    return failures


if __name__ == "__main__":
    sys.exit(main())
