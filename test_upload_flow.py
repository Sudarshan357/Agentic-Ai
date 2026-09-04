from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph import run_workflow
from nodes import extract_text, is_supported_source


PAPER_ONE = """TITLE: Thermal Performance of Urban Green Roofs

Across the twelve buildings measured in this study, green roofs reduced peak
summer surface temperature by 12 to 21 degrees Celsius compared with adjacent
conventional roofing. The cooling effect was strongest on buildings with
shallow substrate depth and dense sedum planting.

Measured reductions in top-floor cooling energy demand ranged from 8 to 15
percent. The authors note that these figures come from a temperate maritime
climate and should not be generalised to arid or tropical settings without
further measurement.

Winter heating benefits were small and inconsistent. In four of the twelve
buildings, no statistically significant heating benefit was observed at all.
"""

PAPER_TWO = """TITLE: Stormwater Retention and Structural Cost of Green Roofs

Green roof installations in this survey retained between 40 and 62 percent of
annual rainfall volume, with retention falling sharply during prolonged
saturation events. Retention performance therefore varies considerably by
season and by storm intensity.

Structural reinforcement was required in 9 of the 23 retrofit projects
examined, adding 14 to 30 percent to total installation cost. Maintenance
obligations continue for the life of the installation and are frequently
underestimated at the planning stage.

The authors conclude that green roofs offer measurable but conditional
benefits, and that performance claims should always be tied to a stated
climate and building type.
"""

PAPER_THREE_PDF_TEXT = """TITLE: Biodiversity Outcomes on Retrofitted Green Roofs

Invertebrate species richness on the monitored green roofs was 2.1 to 3.4
times higher than on control roofs over three survey seasons. Bird foraging
visits increased on sites larger than 400 square metres.

Benefits were markedly lower on roofs using a single sedum species. The study
reports no measurable biodiversity gain on four small installations under 100
square metres.

The authors caution that a green roof is a supplement to ground level habitat
and is not a replacement for it.
"""


def build_pdf(path: str, title: str, body: str) -> None:
    """Write a genuine, minimal, text-bearing PDF that pypdf can read."""
    lines = [title, ""] + [ln for ln in body.splitlines()]

    def esc(text: str) -> str:
        return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    parts = ["BT", "/F1 11 Tf", "50 750 Td", "14 TL"]
    for line in lines:
        parts.append(f"({esc(line[:95])}) Tj")
        parts.append("T*")
    parts.append("ET")
    stream = "\n".join(parts).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + payload + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()

    with open(path, "wb") as handle:
        handle.write(bytes(out))


def build_corpus() -> str:
    """Create the uploaded-sources folder the graph will read."""
    folder = tempfile.mkdtemp(prefix="test_upload_")
    with open(os.path.join(folder, "green_roofs_thermal.txt"), "w", encoding="utf-8") as fh:
        fh.write(PAPER_ONE)
    with open(os.path.join(folder, "green_roofs_stormwater.txt"), "w", encoding="utf-8") as fh:
        fh.write(PAPER_TWO)
    build_pdf(
        os.path.join(folder, "green_roofs_biodiversity.pdf"),
        "TITLE: Biodiversity Outcomes on Retrofitted Green Roofs",
        PAPER_THREE_PDF_TEXT,
    )
    return folder


def main() -> int:
    failures = 0
    folder = build_corpus()
    print("=" * 72)
    print("UPLOAD -> READ -> SUMMARIZE -> FACT CHECK -> LOOP -> CORRECT -> VERIFY")
    print("=" * 72)

    try:
        print("\n1. Uploaded corpus")
        names = sorted(f for f in os.listdir(folder) if is_supported_source(f))
        print(f"   files: {names}")
        if len(names) != 3:
            print("   [FAIL] expected 3 uploaded sources")
            failures += 1

        pdf_text = extract_text(os.path.join(folder, "green_roofs_biodiversity.pdf"))
        pdf_ok = "biodiversity" in pdf_text.lower() or "invertebrate" in pdf_text.lower()
        print(f"   [{'PASS' if pdf_ok else 'FAIL'}] PDF text extracted "
              f"({len(pdf_text)} chars)")
        if not pdf_ok:
            failures += 1
            print("   extracted:", repr(pdf_text[:200]))

        print("\n2. Running the graph (real model, please wait)")
        seen: list[str] = []
        started = time.time()

        def on_event(node_name, _state):
            seen.append(node_name)
            print(f"   . {node_name}")

        result = run_workflow(
            sources_dir=folder,
            model="qwen2.5:3b",
            max_iterations=3,
            demo_mode=True,
            on_event=on_event,
        )
        elapsed = time.time() - started

        print(f"\n3. Result after {elapsed:.0f}s")
        summaries = result.get("summary_history", [])
        claims_history = result.get("claims_history", [])
        trace = result.get("trace", [])

        print(f"   iterations   : {result.get('iteration')}")
        print(f"   verified     : {result.get('is_verified')}")
        print(f"   summaries    : {len(summaries)}")
        print(f"   fact checks  : {len(claims_history)}")
        print(f"   trace events : {len(trace)}")
        print(f"   nodes visited: {seen}")

        checks = [
            ("read_source ran first", seen[:1] == ["read_source"]),
            ("the uploaded files reached the graph",
             sorted(result.get("sources", [])) == names),
            ("the PDF reached the graph state",
             any(s.endswith(".pdf") for s in result.get("sources", []))),
            ("source_content is non-empty",
             len(result.get("source_content", "")) > 500),
            ("summarize ran at least twice (the loop fired)",
             len(summaries) >= 2),
            ("fact_check ran at least twice", len(claims_history) >= 2),
            ("the graph looped back to summarize",
             seen.count("summarize") >= 2),
            ("the first pass found an unsupported claim",
             any(c["status"] != "SUPPORTED" for c in (claims_history[0] if claims_history else []))),
            ("the final summary is verified", result.get("is_verified") is True),
            ("no injected over-claim survives",
             "zero drawbacks" not in (result.get("summary", "") or "").lower()),
        ]
        print()
        for label, ok in checks:
            print(f"   [{'PASS' if ok else 'FAIL'}] {label}")
            if not ok:
                failures += 1


        print("\n4. Final result panel")
        import ui

        rejected = ""
        for pass_claims in result.get("claims_history", []):
            for claim in pass_claims:
                if claim["status"] == "UNSUPPORTED":
                    rejected = claim["text"]
                    break
            if rejected:
                break

        panel = ui.final_result_panel(
            result,
            source_count=len(result.get("sources", [])),
            rejected_claim=rejected,
            rejected_reason="",
        )
        print(f"   injected claim : {rejected!r}")

        subject_words = {"green", "roofs"}
        panel_checks = [
            ("panel states FINAL VERDICT", "Final verdict" in panel),
            ("panel shows VERIFIED", "VERIFIED" in panel),
            ("panel shows the final verified summary",
             (result.get("summary", "")[:40] or "x") in panel),
            ("panel shows Sources analyzed", "Sources analyzed" in panel),
            ("panel shows Iterations", "Iterations" in panel),
            ("panel shows Correction loops", "Correction loops" in panel),
            ("panel shows Claims verified", "Claims verified" in panel),
            ("panel shows the correction detected", "Correction detected" in panel),
            ("panel shows the journey", "Uploaded Papers" in panel),
            ("the injected claim is about the uploaded topic",
             bool(subject_words & set(rejected.lower().split()))),
        ]
        for label, ok in panel_checks:
            print(f"   [{'PASS' if ok else 'FAIL'}] {label}")
            if not ok:
                failures += 1

        print("\n   FINAL SUMMARY\n   " + "-" * 60)
        for line in (result.get("summary") or "").splitlines():
            print("   " + line)

    finally:
        shutil.rmtree(folder, ignore_errors=True)

    print("\n" + "=" * 72)
    print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
    print("=" * 72)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
