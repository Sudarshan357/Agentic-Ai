from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request

import streamlit as st
import streamlit.components.v1 as components

import ui
from graph import run_workflow
from nodes import extract_text, is_supported_source

HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL = "http://127.0.0.1:11434"

st.set_page_config(
    page_title="Multi-Step Research Summarizer",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(ui.CSS, unsafe_allow_html=True)
st.markdown(ui.EXTRA_CSS, unsafe_allow_html=True)
st.markdown(ui.FINAL_CSS, unsafe_allow_html=True)
st.markdown(ui.TOOLBAR_CSS, unsafe_allow_html=True)

st.session_state.setdefault("result", None)
st.session_state.setdefault("pending", None)
st.session_state.setdefault("elapsed", 0.0)
st.session_state.setdefault("upload_dir", None)


def ollama_models() -> list[str] | None:
    """Return the locally installed model names, or None if Ollama is down."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        return [m["name"] for m in data.get("models", [])]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def upload_dir() -> str:
    """Per-session folder the graph reads the uploaded papers from."""
    existing = st.session_state.get("upload_dir")
    if existing and os.path.isdir(existing):
        return existing
    created = tempfile.mkdtemp(prefix="research_sources_")
    st.session_state.upload_dir = created
    return created


def save_uploads(files) -> list[str]:
    """Write the uploaded papers into the session folder, replacing any previous set."""
    target = upload_dir()
    for stale in os.listdir(target):
        try:
            os.remove(os.path.join(target, stale))
        except OSError:
            pass

    saved: list[str] = []
    for item in files:
        name = os.path.basename(item.name)
        with open(os.path.join(target, name), "wb") as handle:
            handle.write(item.getbuffer())
        saved.append(name)
    return sorted(saved)


def list_sources() -> list[str]:
    target = st.session_state.get("upload_dir")
    if not target or not os.path.isdir(target):
        return []
    return sorted(f for f in os.listdir(target) if is_supported_source(f))


def load_documents() -> tuple[list[dict], list[str]]:
    """Documents for the preview panel, plus any per-file extraction errors."""
    documents: list[dict] = []
    problems: list[str] = []
    target = st.session_state.get("upload_dir") or ""
    for name in list_sources():
        try:
            content = extract_text(os.path.join(target, name))
        except (ValueError, RuntimeError, OSError) as error:
            problems.append(str(error))
            continue
        documents.append(
            {"name": name, "content": content, "words": len(content.split())}
        )
    return documents, problems


def render_journey(slot, state: dict | None, finished: bool = False) -> None:
    slot.markdown(
        ui.journey_stepper(ui.journey_status(state, finished=finished)),
        unsafe_allow_html=True,
    )


def first_rejected_claim(state: dict) -> str:
    claim, _ = first_rejection(state)
    return claim


def first_rejection(state: dict) -> tuple[str, str]:
    """The first rejected claim and the reason given, for the final panel."""
    for claims in state.get("claims_history", []):
        for claim in claims:
            if claim["status"] == "UNSUPPORTED":
                return claim["text"], claim.get("reason", "")
    return "", ""


def diagram_state_after(node_name: str, state: dict) -> tuple[dict, bool, bool]:
    """Translate "node X just finished" into diagram highlighting."""
    verified = bool(state.get("is_verified"))
    will_loop = (
        node_name == "fact_check"
        and not verified
        and state.get("iteration", 0) < state.get("max_iterations", 3)
    )

    if node_name == "read_source":
        return {"read_source": "done", "summarize": "active"}, False, False
    if node_name == "summarize":
        return (
            {"read_source": "done", "summarize": "done", "fact_check": "active"},
            False,
            False,
        )
    if node_name == "fact_check":
        states = {
            "read_source": "done",
            "summarize": "done",
            "fact_check": "done" if verified else "failed",
            "decision": "active",
        }
        if will_loop:
            states["summarize"] = "active"
        return states, will_loop, verified
    return (
        {
            "read_source": "done",
            "summarize": "done",
            "fact_check": "done" if verified else "failed",
            "decision": "done",
            "end": "done",
        },
        False,
        verified,
    )


def timeline_rows(state: dict) -> str:
    """Node log rows, with a CONDITIONAL ROUTING row after each loop-back."""
    rows: list[str] = []
    log = state.get("node_log", [])
    max_iterations = state.get("max_iterations", 3)

    for entry in log:
        rows.append(ui.timeline_row(entry["label"], entry["status"]))
        if entry["node"] == "fact_check" and entry["status"] == "warning":
            if entry["iteration"] < max_iterations:
                rows.append(
                    ui.timeline_row("CONDITIONAL ROUTING → summarize", "routing")
                )
    return "".join(rows)


def draw_diagram(slot, node_states=None, loop_active=False, verified=False):
    """Rendered through components.html: Streamlit's markdown sanitiser strips <svg>."""
    with slot.container():
        components.html(
            ui.workflow_diagram(node_states, loop_active, verified),
            height=ui.DIAGRAM_HEIGHT + 12,
            scrolling=False,
        )


def render_live_panel(diagram_ph, timeline_ph, node_states, loop_active, verified, state):
    draw_diagram(diagram_ph, node_states, loop_active, verified)
    timeline_ph.markdown(timeline_rows(state), unsafe_allow_html=True)


def render_metrics(slot, state: dict | None):
    if not state:
        tiles = [
            ui.metric("Workflow status", "IDLE", "waiting to run", ui.INK_SUBTLE),
            ui.metric("Iterations", "0", "summaries generated", ui.INK_SUBTLE),
            ui.metric("Claims verified", "—", "no run yet", ui.INK_SUBTLE),
            ui.metric("Correction loops", "0", "fact_check → summarize", ui.INK_SUBTLE),
        ]
    else:
        verified = state.get("is_verified", False)
        claims = state.get("claims", [])
        supported = sum(1 for c in claims if c["status"] == "SUPPORTED")
        loops = max(0, state.get("iteration", 1) - 1)
        color = ui.SUCCESS if verified else ui.DANGER
        tiles = [
            ui.metric(
                "Workflow status",
                "VERIFIED" if verified else "UNVERIFIED",
                f"{st.session_state.elapsed:.1f}s runtime" if st.session_state.elapsed else "",
                color,
            ),
            ui.metric(
                "Iterations",
                str(state.get("iteration", 0)),
                f"max {state.get('max_iterations', 3)}",
                ui.INK,
            ),
            ui.metric(
                "Claims verified",
                f"{supported}/{len(claims)}",
                "final fact-check pass",
                ui.SUCCESS if supported == len(claims) and claims else ui.WARNING,
            ),
            ui.metric(
                "Correction loops",
                str(loops),
                "fact_check → summarize",
                ui.PRIMARY_HOVER if loops else ui.INK_SUBTLE,
            ),
        ]
    with slot.container():
        for column, tile in zip(st.columns(4), tiles):
            column.markdown(tile, unsafe_allow_html=True)


with st.sidebar:
    st.markdown(
        '<div style="font-size:15px;font-weight:600;letter-spacing:-.2px;'
        'display:flex;align-items:center;gap:9px;margin-bottom:2px;">'
        '<span style="width:10px;height:10px;border-radius:3px;'
        f'background:{ui.PRIMARY};display:inline-block;"></span>'
        "Control Panel</div>"
        '<div style="font-size:12px;color:#62666d;">LangGraph runtime</div>',
        unsafe_allow_html=True,
    )

    source_files = list_sources()

    st.markdown("### Model")
    installed = ollama_models()
    if installed is None:
        st.markdown(
            f'<div class="side-file" style="border-color:{ui.DANGER}44">'
            f'<span class="dot" style="background:{ui.DANGER}"></span>'
            "Ollama not reachable</div>"
            '<div class="side-note">Start it with <code>ollama serve</code>, then reload.</div>',
            unsafe_allow_html=True,
        )
        model = "qwen2.5:3b"
    else:
        options = installed or ["qwen2.5:3b"]
        default = next((i for i, m in enumerate(options) if m.startswith("qwen2.5:3b")), 0)
        model = st.selectbox("Ollama model", options, index=default, label_visibility="collapsed")
        st.markdown(
            f'<div class="side-file"><span class="dot"></span>Ollama online · '
            f"{len(installed)} model(s)</div>",
            unsafe_allow_html=True,
        )

    st.markdown("### Maximum correction attempts")
    max_iterations = st.slider(
        "Maximum correction attempts", 1, 5, 3, label_visibility="collapsed"
    )
    st.markdown(
        '<div class="side-note">Safeguard for the conditional edge. The graph stops '
        "after this many summaries even if claims remain unsupported.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Controlled Demo Mode")
    demo_mode = st.checkbox(
        "Guarantee the correction loop", value=True, key="demo_mode"
    )
    st.markdown(
        '<div class="side-note">ON: one deliberate, documented over-claim is '
        "appended to the <b>first</b> summary only, so the fact-check loop always "
        "fires during a live demonstration. The fact checker is not told about it "
        "and judges it like any other claim. OFF: the model runs untouched.</div>",
        unsafe_allow_html=True,
    )


st.markdown(
    """
<div class="hero">
  <div class="hero-eyebrow"><span class="hero-dot"></span>LangGraph · Ollama · qwen2.5:3b</div>
  <h1>Multi-Step Research Summarizer</h1>
  <p>Autonomous LangGraph workflow with self-correction</p>
  <div class="pipeline">
    <span class="pipeline-step">Read</span><span class="pipeline-arrow">→</span>
    <span class="pipeline-step">Summarize</span><span class="pipeline-arrow">→</span>
    <span class="pipeline-step">Fact Check</span><span class="pipeline-arrow">→</span>
    <span class="pipeline-step">Correct</span><span class="pipeline-arrow">→</span>
    <span class="pipeline-step">Verify</span>
  </div>
</div>""",
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="panel-head">'
    '<span class="step-chip">STEP 1</span>'
    '<span class="panel-title">Upload research sources</span></div>'
    '<div class="panel-note">Upload 2 or 3 research papers as PDF or TXT. They '
    "are the only ground truth in this run: every claim the summarizer writes "
    "is checked against these files and nothing else.</div>",
    unsafe_allow_html=True,
)

uploaded = st.file_uploader(
    "Research papers (PDF or TXT)",
    type=["pdf", "txt"],
    accept_multiple_files=True,
    help="2 or 3 files. Text-based PDFs only - a scanned image has no text to extract.",
    key="uploader",
)

if uploaded:
    signature = [(f.name, f.size) for f in uploaded]
    if st.session_state.get("upload_signature") != signature:
        save_uploads(uploaded)
        st.session_state.upload_signature = signature
        st.session_state.result = None

all_documents, upload_problems = load_documents()
for problem in upload_problems:
    st.error(problem)

count = len(all_documents)
ready = 2 <= count <= 3

if not uploaded:
    st.info("Upload 2 or 3 research papers to begin. Nothing else is used as input.")
elif count == 1:
    st.warning("Only 1 readable source. Upload at least 2 so claims can be cross-checked.")
elif count > 3:
    st.warning(f"{count} sources uploaded. Please upload no more than 3.")

selected: list[str] = [doc["name"] for doc in all_documents]

if all_documents:
    tile_columns = st.columns(len(all_documents), gap="medium")
    for column, doc in zip(tile_columns, all_documents):
        with column:
            st.markdown(ui.source_tile(doc, True), unsafe_allow_html=True)
            with st.expander(f"Preview {doc['name']}"):
                preview = doc["content"][:1200]
                st.text(preview + ("..." if len(doc["content"]) > 1200 else ""))

st.markdown(
    '<div class="panel-head" style="margin-top:14px">'
    '<span class="step-chip">STEP 2</span>'
    '<span class="panel-title">Run the graph</span></div>',
    unsafe_allow_html=True,
)

run_col, note_col = st.columns([1, 2.6], gap="large")
with run_col:
    run_clicked = st.button(
        "▶  RUN RESEARCH",
        disabled=not ready or installed is None,
        use_container_width=True,
        key="run_main",
    )
with note_col:
    words = sum(doc["words"] for doc in all_documents)
    st.markdown(
        f'<div class="side-note" style="margin-top:8px">'
        f"{count} source(s) uploaded &middot; {words} words extracted</div>",
        unsafe_allow_html=True,
    )

if run_clicked:
    st.session_state.pending = {
        "model": model,
        "max_iterations": max_iterations,
        "demo_mode": demo_mode,
        "sources_dir": upload_dir(),
        "selected_sources": selected,
    }
    st.session_state.result = None
    st.rerun()


st.markdown('<div class="section-title" style="margin-top:18px">Primary journey</div>'
            '<div class="section-sub">Every stage below is driven by the graph, not by the UI.</div>',
            unsafe_allow_html=True)
journey_slot = st.empty()
render_journey(journey_slot, st.session_state.result, finished=bool(st.session_state.result))

metrics_slot = st.empty()
render_metrics(metrics_slot, st.session_state.result)

tab_workflow, tab_sources, tab_facts, tab_trace, tab_arch = st.tabs(
    ["  Workflow  ", "  Sources  ", "  Fact Check  ", "  Full Trace  ", "  Architecture  "]
)


with tab_workflow:
    left, right = st.columns([1.15, 1], gap="large")

    with left:
        st.markdown('<div class="section-title">Graph execution</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">The active node pulses. When the fact checker '
            "rejects a summary, the conditional edge back to <b>summarize</b> lights up."
            "</div>",
            unsafe_allow_html=True,
        )
        diagram_slot = st.empty()

    with right:
        st.markdown('<div class="section-title">Node timeline</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">One row per completed LangGraph node.</div>',
            unsafe_allow_html=True,
        )
        progress_slot = st.empty()
        timeline_slot = st.empty()

    routing_container = st.container()
    verdict_slot = st.container()
    comparison_slot = st.container()

    if st.session_state.pending:
        config = st.session_state.pending
        draw_diagram(diagram_slot)
        progress_bar = progress_slot.progress(0.0, text="Starting graph…")
        routing_slot = routing_container.empty()
        expected_nodes = 2 + 2 * config["max_iterations"]
        started = time.time()

        def on_event(node_name: str, state: dict) -> None:
            node_states, loop_active, verified = diagram_state_after(node_name, state)
            render_live_panel(
                diagram_slot, timeline_slot, node_states, loop_active, verified, state
            )
            done = len(state.get("node_log", []))
            label = {
                "read_source": "Sources loaded into graph state",
                "summarize": f"Summary generated (iteration {state.get('iteration', 1)})",
                "fact_check": "Claims verified against sources"
                if verified
                else "Unsupported claim detected — routing back to summarize",
                "finalize": "Workflow finished",
            }.get(node_name, node_name)
            progress_bar.progress(
                1.0 if node_name == "finalize" else min(0.95, done / expected_nodes),
                text=label,
            )
            render_metrics(metrics_slot, state)
            render_journey(journey_slot, state)
            if loop_active:
                routing_slot.markdown(
                    ui.routing_banner(
                        state.get("iteration", 1),
                        first_rejected_claim(state),
                        live=True,
                    ),
                    unsafe_allow_html=True,
                )
                time.sleep(1.8)

        try:
            result = run_workflow(
                sources_dir=config["sources_dir"],
                model=config["model"],
                max_iterations=config["max_iterations"],
                demo_mode=config["demo_mode"],
                selected_sources=config.get("selected_sources"),
                on_event=on_event,
            )
            st.session_state.elapsed = time.time() - started
            st.session_state.result = result
        except Exception as error:  # noqa: BLE001 - surfaced to the user
            st.session_state.result = None
            st.error(
                f"Workflow failed: {error}\n\n"
                "Check that Ollama is running (`ollama serve`) and that the model "
                "has been pulled (`ollama pull qwen2.5:3b`)."
            )
        finally:
            st.session_state.pending = None

        if st.session_state.result:
            st.rerun()

    result = st.session_state.result
    if result:
        node_states, _, verified = diagram_state_after("finalize", result)
        draw_diagram(diagram_slot, node_states, False, verified)
        progress_slot.progress(
            1.0,
            text="Summary verified" if verified else "Stopped at the iteration safeguard",
        )
        timeline_slot.markdown(timeline_rows(result), unsafe_allow_html=True)

        history = result.get("summary_history", [])
        if len(history) > 1:
            with routing_container:
                st.markdown(
                    ui.routing_banner(1, first_rejected_claim(result)),
                    unsafe_allow_html=True,
                )
        claims_history = result.get("claims_history", [])

        rejected_text, rejected_reason = first_rejection(result)
        with verdict_slot:
            st.markdown(
                ui.final_result_panel(
                    result,
                    source_count=len(result.get("sources", [])),
                    rejected_claim=rejected_text,
                    rejected_reason=rejected_reason,
                ),
                unsafe_allow_html=True,
            )

        with comparison_slot:
            st.markdown(
                '<div class="section-title">Summary comparison</div>'
                '<div class="section-sub">Before and after the self-correction loop.</div>',
                unsafe_allow_html=True,
            )

            if len(history) > 1:
                first_unsupported = [
                    c["text"] for c in claims_history[0] if c["status"] == "UNSUPPORTED"
                ]
                col_a, col_b = st.columns(2, gap="large")

                with col_a:
                    st.markdown(
                        f'<div class="card-title">{ui.badge("✕ ITERATION 1 · REJECTED", ui.DANGER)}</div>'
                        f'<div class="summary-box" style="border-left:2px solid {ui.DANGER}">'
                        f"{ui.highlight_unsupported(history[0], first_unsupported)}</div>",
                        unsafe_allow_html=True,
                    )

                with col_b:
                    label = (
                        f"✓ ITERATION {len(history)} · VERIFIED"
                        if verified
                        else f"! ITERATION {len(history)} · STILL UNVERIFIED"
                    )
                    color = ui.SUCCESS if verified else ui.WARNING
                    final_unsupported = result.get("unsupported_claims", [])
                    st.markdown(
                        f'<div class="card-title">{ui.badge(label, color)}</div>'
                        f'<div class="summary-box" style="border-left:2px solid {color}">'
                        f"{ui.highlight_unsupported(history[-1], final_unsupported)}</div>",
                        unsafe_allow_html=True,
                    )

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                feedback = (result.get("feedback_history") or [""])[0]
                st.markdown(
                    '<div class="card card-accent" style="border-left-color:'
                    f'{ui.WARNING}">'
                    f'<div class="card-title">{ui.badge("⚠ FACT-CHECK FEEDBACK SENT BACK TO THE SUMMARIZER", ui.WARNING)}</div>'
                    f'<pre class="trace-body">{ui.pre_text(feedback)}</pre></div>',
                    unsafe_allow_html=True,
                )
            else:
                color = ui.SUCCESS if verified else ui.WARNING
                st.markdown(
                    f'<div class="card-title">{ui.badge("✓ VERIFIED ON THE FIRST PASS", color)}</div>'
                    f'<div class="summary-box" style="border-left:2px solid {color}">'
                    f"{ui._escape(history[-1] if history else '')}</div>",
                    unsafe_allow_html=True,
                )
                st.info(
                    "The first summary passed the fact check, so the correction loop "
                    "was not needed. Enable **Controlled Demo Mode** in the "
                    "sidebar to force the loop for a demonstration."
                )
    elif not st.session_state.pending:
        draw_diagram(diagram_slot)
        timeline_slot.markdown(
            '<div class="card"><div class="card-body">Press '
            "<b>Run Autonomous Research</b> in the research input panel above "
            "to execute the graph.</div></div>",
            unsafe_allow_html=True,
        )


with tab_sources:
    st.markdown(
        '<div class="section-title">Research sources</div>'
        '<div class="section-sub">The uploaded research papers, as processed by '
        "the <b>read_source</b> node. These are the ground truth every claim is "
        "checked against.</div>",
        unsafe_allow_html=True,
    )

    documents = (st.session_state.result or {}).get("source_documents")
    if not documents:
        documents, _ = load_documents()

    if documents:
        for column, doc in zip(st.columns(len(documents)), documents):
            title = doc["content"].splitlines()[0].replace("TITLE:", "").strip()
            column.markdown(
                f'<div class="card"><div class="card-title">'
                f'<span style="color:{ui.PRIMARY}">◆</span>{doc["name"]}</div>'
                f'<div class="card-body" style="font-size:13.5px">{ui._escape(title)}</div>'
                f'<div style="margin-top:10px">{ui.badge(f"{doc["words"]} words", ui.INK_SUBTLE)}</div>'
                "</div>",
                unsafe_allow_html=True,
            )

        for doc in documents:
            with st.expander(f"Read {doc['name']}"):
                st.code(doc["content"], language="text")
    else:
        st.warning("No research sources uploaded yet. Upload 2 or 3 PDF or TXT papers above.")


with tab_facts:
    st.markdown(
        '<div class="section-title">Claim-level verification</div>'
        '<div class="section-sub">The <b>fact_check</b> node splits the summary into '
        "sentences and judges each one against the sources.</div>",
        unsafe_allow_html=True,
    )

    result = st.session_state.result
    if not result:
        st.markdown(
            '<div class="card"><div class="card-body">No run yet. Execute the '
            "workflow to see claim-by-claim results.</div></div>",
            unsafe_allow_html=True,
        )
    else:
        for index, claims in enumerate(result.get("claims_history", []), start=1):
            bad = sum(1 for c in claims if c["status"] == "UNSUPPORTED")
            headline = (
                f"Iteration {index} — {len(claims)} claims checked · "
                + ("all supported ✓" if not bad else f"{bad} unsupported ✕")
            )
            with st.expander(headline, expanded=(index == len(result["claims_history"]))):
                for claim in claims:
                    st.markdown(ui.claim_card(claim), unsafe_allow_html=True)

                verdict_color = ui.SUCCESS if not bad else ui.DANGER
                verdict_text = (
                    "FINAL DECISION: SUMMARY VERIFIED → route to END"
                    if not bad
                    else "FINAL DECISION: UNSUPPORTED CLAIM DETECTED → route back to SUMMARIZE"
                )
                st.markdown(
                    f'<div class="card" style="border-left:2px solid {verdict_color}">'
                    f'<div class="card-title" style="color:{verdict_color}">{verdict_text}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )


with tab_trace:
    st.markdown(
        '<div class="section-title">Execution trace</div>'
        '<div class="section-sub">Every node writes one entry into '
        "<code>state[\"trace\"]</code> as it runs.</div>",
        unsafe_allow_html=True,
    )

    result = st.session_state.result
    if not result:
        st.markdown(
            '<div class="card"><div class="card-body">No trace yet — run the '
            "workflow first.</div></div>",
            unsafe_allow_html=True,
        )
    else:
        colors = {
            "completed": ui.SUCCESS,
            "warning": ui.WARNING,
            "error": ui.DANGER,
            "routing": ui.PRIMARY_HOVER,
        }
        events = result.get("trace", [])
        for position, event in enumerate(events):
            color = colors.get(event["status"], ui.INK_SUBTLE)
            st.markdown(
                f'<div class="trace-block" style="border-left-color:{color}">'
                f'<div class="trace-head"><span class="trace-step">[{event["step"]}]</span>'
                f'<span style="color:{color}">{event["title"]}</span>'
                f'<span style="margin-left:auto;font-size:11px;color:{ui.INK_TERTIARY};'
                f'font-weight:400">node: {event["node"]}</span></div>'
                f'<pre class="trace-body">{ui.pre_text(event["body"])}</pre></div>',
                unsafe_allow_html=True,
            )

            if (
                event["node"] == "fact_check"
                and event["status"] == "warning"
                and position + 1 < len(events)
                and events[position + 1]["node"] == "summarize"
            ):
                st.markdown(
                    f'<div class="trace-connector">↓</div>'
                    f'<div class="trace-block" style="border-left-color:{ui.PRIMARY_HOVER};'
                    f'background:{ui.SURFACE_2}">'
                    f'<div class="trace-head"><span class="trace-step">↻</span>'
                    f'<span style="color:{ui.PRIMARY_HOVER}">CONDITIONAL ROUTING ACTIVATED</span></div>'
                    '<pre class="trace-body">Unsupported claims detected.<br>'
                    "route_after_fact_check() returned &quot;summarize&quot;.<br><br>"
                    "Routing workflow back to: SUMMARIZE NODE</pre></div>",
                    unsafe_allow_html=True,
                )
            elif position + 1 < len(events):
                st.markdown('<div class="trace-connector">↓</div>', unsafe_allow_html=True)

        with st.expander("Raw final state (JSON)"):
            printable = {
                key: value
                for key, value in result.items()
                if key not in {"source_content", "source_documents", "trace"}
            }
            st.json(printable)


with tab_arch:
    st.markdown(
        '<div class="section-title">How the graph is built</div>'
        '<div class="section-sub">Four nodes, three fixed edges, and one conditional '
        "edge that can send execution backwards.</div>",
        unsafe_allow_html=True,
    )

    arch_left, arch_right = st.columns([1, 1.1], gap="large")

    with arch_left:
        components.html(ui.workflow_diagram(), height=ui.DIAGRAM_HEIGHT + 12, scrolling=False)

    with arch_right:
        explanations = [
            (
                "read_source",
                "Node 1 · Read Source",
                "Processes the uploaded research sources — PDF or TXT — and writes "
                "their combined text into the graph state. No LLM is used here; it is "
                "the ground truth the fact checker later compares against.",
            ),
            (
                "summarize",
                "Node 2 · Summarize",
                "Calls qwen2.5:3b through Ollama to write a 4–6 sentence summary. On "
                "iteration 1 it summarizes from scratch; from iteration 2 the "
                "fact-check feedback is already in the state, so it rewrites instead.",
            ),
            (
                "fact_check",
                "Node 3 · Fact Check",
                "Splits the summary into sentence-level claims and asks the model to "
                "judge each one against the sources as SUPPORTED, PARTIAL or "
                "UNSUPPORTED, with a reason and the evidence sentence it used.",
            ),
            (
                "router",
                "Conditional Router",
                "route_after_fact_check() reads the state. Unsupported claims left and "
                "iterations remaining → return \"summarize\" and the graph loops back. "
                "Otherwise → return \"finish\" and the graph moves to finalize, then END.",
            ),
            (
                "loop",
                "The Feedback Loop",
                "The fact checker's verdicts are turned into written feedback stored in "
                "state[\"fact_check_feedback\"]. Because state travels along every edge, "
                "the summarize node receives that feedback when the loop closes — this "
                "is what makes the system self-correcting rather than merely repetitive.",
            ),
            (
                "safeguard",
                "Iteration Safeguard",
                "max_iterations (default 3) caps the number of summaries. If the "
                "summary still fails after the last attempt, the router sends the graph "
                "to finalize with a VERIFICATION FAILED verdict instead of looping "
                "forever.",
            ),
        ]
        for key, title, text in explanations:
            st.markdown(
                f'<div class="card card-accent"><div class="card-title">'
                f'<span style="font-family:JetBrains Mono,monospace;font-size:11px;'
                f'color:{ui.PRIMARY_HOVER}">{key}</span></div>'
                f'<div style="font-size:14.5px;font-weight:600;margin-bottom:6px">{title}</div>'
                f'<div class="card-body" style="font-size:14px">{text}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="section-title">The graph definition</div>'
        '<div class="section-sub">Taken verbatim from <code>graph.py</code>.</div>',
        unsafe_allow_html=True,
    )
    st.code(
        '''graph = StateGraph(ResearchState)

# 1. NODES
graph.add_node("read_source", read_source)
graph.add_node("summarize",   summarize)
graph.add_node("fact_check",  fact_check)
graph.add_node("finalize",    finalize)

# 2. FIXED EDGES
graph.add_edge(START,         "read_source")
graph.add_edge("read_source", "summarize")
graph.add_edge("summarize",   "fact_check")

# 3. CONDITIONAL EDGE — the self-correction loop
graph.add_conditional_edges(
    "fact_check",
    route_after_fact_check,          # inspects state, returns a key
    {
        "summarize": "summarize",    # unsupported claims -> loop back
        "finish":    "finalize",     # verified / safeguard -> stop
    },
)

graph.add_edge("finalize", END)

app = graph.compile()''',
        language="python",
    )

    st.markdown(
        f'<div class="card"><div class="card-title">'
        f'<span style="color:{ui.PRIMARY}">◆</span>Why this is a graph, not a script</div>'
        '<div class="card-body">A sequential script runs each function once, in a fixed '
        "order decided when the code was written. Here the <i>state</i> decides the "
        "order at runtime: the same <code>summarize</code> node is entered from two "
        "different edges — once from <code>read_source</code>, and again from the "
        "conditional edge after a failed fact check. That cycle is what makes the "
        "workflow autonomous and self-correcting.</div></div>",
        unsafe_allow_html=True,
    )
