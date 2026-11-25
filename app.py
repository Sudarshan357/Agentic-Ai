from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.request

import streamlit as st
import streamlit.components.v1 as components

import memory
import ui
from graph import new_thread_id, resume_workflow, run_workflow, thread_messages
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
st.session_state.setdefault("thread_id", new_thread_id())


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


def _reset_upload_dir() -> str:
    """Clear any previous files in the session upload folder and return its path."""
    target = upload_dir()
    for stale in os.listdir(target):
        try:
            os.remove(os.path.join(target, stale))
        except OSError:
            pass
    return target


def save_uploads(files) -> list[str]:
    """Write the uploaded papers into the session folder, replacing any previous set."""
    target = _reset_upload_dir()
    saved: list[str] = []
    for item in files:
        name = os.path.basename(item.name)
        with open(os.path.join(target, name), "wb") as handle:
            handle.write(item.getbuffer())
        saved.append(name)
    return sorted(saved)


def load_sample_sources(sample_dir: str, filenames: list[str]) -> list[str]:
    """Copy bundled sample papers into the session folder."""
    target = _reset_upload_dir()
    for name in filenames:
        shutil.copyfile(os.path.join(sample_dir, name), os.path.join(target, name))
    return sorted(filenames)


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


AGENT_NODES = ("summarizer", "fact_checker", "guard", "human_review")


def diagram_state_after(node_name: str, state: dict) -> tuple[dict, str, str]:
    """Translate "node X just finished" into diagram highlighting."""
    node_states: dict[str, str] = {}
    for entry in state.get("node_log", []):
        bad = entry["status"] in {"warning", "error"} and entry["node"] != "supervisor"
        node_states[entry["node"]] = "failed" if bad else "done"

    active_edge = ""
    final = state.get("final_status")
    if state.get("awaiting_approval"):
        node_states["human_review"] = "waiting"
        active_edge = "human_review"
    elif not final:
        if node_name == "read_source":
            node_states["index_sources"] = "active"
        elif node_name == "index_sources":
            node_states["supervisor"] = "active"
        elif node_name == "supervisor":
            nxt = state.get("next_agent", "")
            node_states[nxt] = "active"
            active_edge = nxt
        elif node_name in AGENT_NODES:
            node_states["supervisor"] = "active"
            active_edge = node_name

    hops = f"hop {state.get('hops', 0)}/{state.get('max_hops', 0)}" if state.get("max_hops") else ""
    return node_states, active_edge, hops


def rerouted_to_summarizer(node_name: str, state: dict) -> bool:
    """True right after the supervisor sends a rejected draft back."""
    return (
        node_name == "supervisor"
        and state.get("next_agent") == "summarizer"
        and state.get("iteration", 0) >= 1
    )


def timeline_rows(state: dict) -> str:
    """One row per node that ran, supervisor hand-offs included."""
    rows = [ui.timeline_row(e["label"], e["status"]) for e in state.get("node_log", [])]
    if state.get("awaiting_approval"):
        rows.append(ui.timeline_row("HUMAN APPROVAL", "waiting"))
    return "".join(rows)


def draw_diagram(slot, node_states=None, active_edge="", hops=""):
    """Rendered through components.html: Streamlit's markdown sanitiser strips <svg>."""
    with slot.container():
        components.html(
            ui.workflow_diagram(node_states, active_edge, hops),
            height=ui.DIAGRAM_HEIGHT + 12,
            scrolling=False,
        )


def render_live_panel(diagram_ph, timeline_ph, node_name, state):
    draw_diagram(diagram_ph, *diagram_state_after(node_name, state))
    timeline_ph.markdown(timeline_rows(state), unsafe_allow_html=True)


def render_metrics(slot, state: dict | None):
    if not state:
        tiles = [
            ui.metric("Workflow status", "IDLE", "waiting to run", ui.INK_SUBTLE),
            ui.metric("Iterations", "0", "summaries generated", ui.INK_SUBTLE),
            ui.metric("Claims verified", "—", "no run yet", ui.INK_SUBTLE),
            ui.metric("Supervisor hops", "0", "agent hand-offs", ui.INK_SUBTLE),
        ]
    else:
        final = state.get("final_status", "")
        if state.get("awaiting_approval"):
            label, color = "AWAITING APPROVAL", ui.WARNING
        elif final:
            label = final
            color = ui.SUCCESS if final in {"APPROVED", "VERIFIED"} else ui.DANGER
        else:
            label, color = "RUNNING", ui.PRIMARY_HOVER
        claims = state.get("claims", [])
        supported = sum(1 for c in claims if c["status"] == "SUPPORTED")
        hops, max_hops = state.get("hops", 0), state.get("max_hops", 0)
        tiles = [
            ui.metric(
                "Workflow status",
                label,
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
                "latest fact-check pass",
                ui.SUCCESS if supported == len(claims) and claims else ui.WARNING,
            ),
            ui.metric(
                "Supervisor hops",
                f"{hops}/{max_hops}",
                "hop limit stops the run" if state.get("hop_limit_hit") else "agent hand-offs",
                ui.DANGER if state.get("hop_limit_hit") else ui.PRIMARY_HOVER,
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

    st.markdown("### Supervisor hop limit")
    max_hops = st.slider("Supervisor hop limit", 4, 20, 12, label_visibility="collapsed")
    st.markdown(
        '<div class="side-note">Each time the supervisor hands work to an agent '
        "counts as one hop. At the limit it stops the run instead of looping.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Human approval")
    require_approval = st.checkbox("Pause for my approval before finishing", value=True)
    st.markdown(
        '<div class="side-note">The graph pauses with <code>interrupt()</code> after the '
        "guard agent passes. Approve, or send notes back to the summarizer.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Memory")
    embed_ok = installed is not None and any(
        m.startswith(memory.EMBED_MODEL) for m in installed
    )
    st.markdown(
        f'<div class="side-file"{"" if embed_ok else f" style=border-color:{ui.DANGER}44"}>'
        f'<span class="dot"{"" if embed_ok else f" style=background:{ui.DANGER}"}></span>'
        f"{memory.EMBED_MODEL} {'ready' if embed_ok else 'missing'}</div>"
        + (
            ""
            if embed_ok
            else '<div class="side-note">Run <code>ollama pull nomic-embed-text</code>.</div>'
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="side-note">Thread (short-term memory):<br>'
        f'<code>{st.session_state.thread_id}</code></div>',
        unsafe_allow_html=True,
    )
    if st.button("Start a new thread", width="stretch"):
        st.session_state.thread_id = new_thread_id()
        st.session_state.result = None
        st.rerun()
    lesson_count = len(memory.all_lessons(memory.get_store(), limit=500)) if embed_ok else 0
    st.markdown(
        f'<div class="side-note">Long-term memory: {lesson_count} lesson(s) in '
        "<code>memory_data/store.sqlite</code></div>",
        unsafe_allow_html=True,
    )
    if lesson_count and st.button("Clear long-term memory", width="stretch"):
        memory.clear_long_term(memory.get_store())
        st.rerun()


st.markdown(
    """
<div class="hero">
  <div class="hero-eyebrow"><span class="hero-dot"></span>LangGraph supervisor · Ollama · Chroma RAG · SQLite memory</div>
  <h1>Multi-Step Research Summarizer</h1>
  <p>A supervisor routes the work between a summarizer, a fact checker and a guard agent, then asks you to approve</p>
  <div class="pipeline">
    <span class="pipeline-step">Read</span><span class="pipeline-arrow">→</span>
    <span class="pipeline-step">Index (RAG)</span><span class="pipeline-arrow">→</span>
    <span class="pipeline-step">Supervisor</span><span class="pipeline-arrow">⇄</span>
    <span class="pipeline-step">Agents</span><span class="pipeline-arrow">→</span>
    <span class="pipeline-step">Human approval</span>
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

sample_dir = os.path.join(HERE, "sources")
sample_files = (
    sorted(f for f in os.listdir(sample_dir) if is_supported_source(f))
    if os.path.isdir(sample_dir)
    else []
)
if 2 <= len(sample_files) <= 3:
    if st.button("Load sample papers (demo corpus)", key="load_samples"):
        load_sample_sources(sample_dir, sample_files)
        st.session_state.upload_signature = [("sample", name) for name in sample_files]
        st.session_state.result = None
        st.rerun()

all_documents, upload_problems = load_documents()
for problem in upload_problems:
    st.error(problem)

count = len(all_documents)
ready = 2 <= count <= 3

if not all_documents and not uploaded:
    st.info("Upload 2 or 3 research papers (or load the sample papers) to begin. Nothing else is used as input.")
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
        disabled=not ready or installed is None or not embed_ok,
        width="stretch",
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
        "kind": "start",
        "thread_id": st.session_state.thread_id,
        "max_hops": max_hops,
        "require_approval": require_approval,
        "model": model,
        "max_iterations": max_iterations,
        "demo_mode": demo_mode,
        "sources_dir": upload_dir(),
        "selected_sources": selected,
    }
    st.session_state.result = None
    st.session_state.elapsed = 0.0
    st.rerun()


st.markdown('<div class="section-title" style="margin-top:18px">Primary journey</div>'
            '<div class="section-sub">Every stage below is driven by the graph, not by the UI.</div>',
            unsafe_allow_html=True)
journey_slot = st.empty()
render_journey(journey_slot, st.session_state.result, finished=bool(st.session_state.result))

metrics_slot = st.empty()
render_metrics(metrics_slot, st.session_state.result)

waiting = st.session_state.result or {}
if waiting.get("awaiting_approval") and not st.session_state.pending:
    with st.container(border=True):
        st.markdown(
            f'<div class="card-title">{ui.badge("⏸ HUMAN APPROVAL REQUIRED", ui.WARNING)}</div>'
            '<div class="section-sub">The fact checker and the guard agent passed this '
            "draft. The graph is paused on thread "
            f"<code>{waiting.get('thread_id', '')}</code> until you decide.</div>"
            f'<div class="summary-box" style="border-left:2px solid {ui.WARNING}">'
            f"{ui._escape(waiting['awaiting_approval'].get('summary', ''))}</div>",
            unsafe_allow_html=True,
        )
        notes = st.text_area(
            "Notes for the summarizer (used if you request changes)",
            key=f"review_notes_{waiting.get('thread_id')}_{waiting.get('iteration')}",
            placeholder="e.g. Mention the sample size and keep the caveat about climate.",
        )
        approve_col, reject_col, _ = st.columns([1, 1, 2])
        approve = approve_col.button("✓  Approve", width="stretch", key="approve")
        reject = reject_col.button("✕  Request changes", width="stretch", key="reject")
        if approve or reject:
            st.session_state.pending = {
                "kind": "resume",
                "thread_id": waiting["thread_id"],
                "approved": bool(approve),
                "feedback": notes,
            }
            st.rerun()

tab_workflow, tab_sources, tab_facts, tab_memory, tab_trace, tab_arch = st.tabs(
    [
        "  Workflow  ",
        "  Sources  ",
        "  Fact Check  ",
        "  Memory & RAG  ",
        "  Full Trace  ",
        "  Architecture  ",
    ]
)


with tab_workflow:
    left, right = st.columns([1.15, 1], gap="large")

    with left:
        st.markdown('<div class="section-title">Graph execution</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">The active agent pulses. Every agent reports back '
            "to the <b>supervisor</b>, which lights up the edge to whoever goes next."
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
        previous = st.session_state.result or {}
        draw_diagram(diagram_slot, *diagram_state_after("", previous) if previous else ())
        progress_bar = progress_slot.progress(
            0.0, text="Resuming the paused thread…" if config["kind"] == "resume" else "Starting graph…"
        )
        routing_slot = routing_container.empty()
        started = time.time()

        def on_event(node_name: str, state: dict) -> None:
            render_live_panel(diagram_slot, timeline_slot, node_name, state)
            label = {
                "read_source": "Sources loaded into graph state",
                "index_sources": "Papers embedded into Chroma",
                "supervisor": f"Supervisor → {state.get('next_agent', '')}",
                "summarizer": f"Summarizer wrote draft {state.get('iteration', 1)}",
                "fact_checker": "Claims verified"
                if state.get("is_verified")
                else "Fact checker rejected claims",
                "guard": "Guard passed" if state.get("guard_passed") else "Guard blocked the draft",
                "human_review": "Reviewer decision recorded",
                "finalize": "Workflow finished",
            }.get(node_name, node_name)
            done = len(state.get("node_log", []))
            progress_bar.progress(
                1.0 if node_name == "finalize" else min(0.95, done / 18), text=label
            )
            render_metrics(metrics_slot, state)
            render_journey(journey_slot, state)
            if rerouted_to_summarizer(node_name, state):
                routing_slot.markdown(
                    ui.routing_banner(
                        state.get("iteration", 1), first_rejected_claim(state), live=True
                    ),
                    unsafe_allow_html=True,
                )
                time.sleep(1.2)

        try:
            if config["kind"] == "resume":
                result = resume_workflow(
                    config["thread_id"],
                    approved=config["approved"],
                    feedback=config.get("feedback", ""),
                    on_event=on_event,
                )
            else:
                result = run_workflow(
                    sources_dir=config["sources_dir"],
                    model=config["model"],
                    max_iterations=config["max_iterations"],
                    demo_mode=config["demo_mode"],
                    selected_sources=config.get("selected_sources"),
                    max_hops=config["max_hops"],
                    require_approval=config["require_approval"],
                    thread_id=config["thread_id"],
                    on_event=on_event,
                )
            st.session_state.elapsed += time.time() - started
            st.session_state.result = result
        except Exception as error:  # noqa: BLE001 - surfaced to the user
            st.session_state.result = None
            st.error(
                f"Workflow failed: {error}\n\n"
                "Check that Ollama is running (`ollama serve`) and that both models "
                "are pulled (`ollama pull qwen2.5:3b` and `ollama pull nomic-embed-text`)."
            )
        finally:
            st.session_state.pending = None

        if st.session_state.result:
            st.rerun()

    result = st.session_state.result
    if result:
        draw_diagram(diagram_slot, *diagram_state_after("finalize", result))
        verified = bool(result.get("is_verified"))
        progress_slot.progress(
            1.0,
            text="Paused - waiting for your approval above"
            if result.get("awaiting_approval")
            else f"Finished: {result.get('final_status', '')}",
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
            if result.get("final_status"):
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
        '<div class="section-sub">The <b>fact checker</b> agent splits the summary into '
        "sentences and judges each one against the passages Chroma retrieves for it.</div>",
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
                    "VERDICT: SUMMARY VERIFIED → supervisor sends it to the guard"
                    if not bad
                    else "VERDICT: UNSUPPORTED CLAIMS → supervisor sends it back to the summarizer"
                )
                st.markdown(
                    f'<div class="card" style="border-left:2px solid {verdict_color}">'
                    f'<div class="card-title" style="color:{verdict_color}">{verdict_text}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )



with tab_memory:
    result = st.session_state.result or {}
    mem_left, mem_right = st.columns([1, 1], gap="large")

    with mem_left:
        thread_id = result.get("thread_id") or st.session_state.thread_id
        st.markdown(
            '<div class="section-title">Short-term memory · thread</div>'
            '<div class="section-sub">Saved by the SQLite checkpointer on thread '
            f"<code>{thread_id}</code>. Messages pile up across runs on the same "
            "thread, and the summarizer reads reviewer notes from earlier runs.</div>",
            unsafe_allow_html=True,
        )
        try:
            history = thread_messages(thread_id)
        except Exception:  # noqa: BLE001
            history = []
        if not history:
            st.markdown(
                '<div class="card"><div class="card-body">Nothing on this thread yet.'
                "</div></div>",
                unsafe_allow_html=True,
            )
        runs = sum(1 for m in history if getattr(m, "name", "") == "user")
        if history:
            st.caption(f"{len(history)} messages · {runs} run(s) on this thread")
        for message in history[-30:]:
            who = getattr(message, "name", "") or message.type
            color = {
                "user": ui.INK_SUBTLE,
                "human_reviewer": ui.WARNING,
                "summarizer": ui.PRIMARY_HOVER,
                "fact_checker": ui.SUCCESS,
                "guard": ui.DANGER,
            }.get(who, ui.INK_SUBTLE)
            text = str(message.content)
            st.markdown(
                f'<div class="trace-block" style="border-left-color:{color}">'
                f'<div class="trace-head"><span style="color:{color}">{ui._escape(who)}</span></div>'
                f'<pre class="trace-body">{ui.pre_text(text[:700] + ("…" if len(text) > 700 else ""))}</pre></div>',
                unsafe_allow_html=True,
            )

    with mem_right:
        st.markdown(
            '<div class="section-title">Long-term memory · SQLite store</div>'
            '<div class="section-sub">Lessons written by the fact checker, the guard and the '
            "human reviewer. They outlive threads, and the summarizer looks up the closest "
            "ones by meaning (nomic-embed-text) before it writes.</div>",
            unsafe_allow_html=True,
        )
        recalled = result.get("recalled_lessons") or []
        if recalled:
            st.markdown("**Recalled in this run**")
            for item in recalled:
                score = f" · similarity {item['score']}" if item.get("score") is not None else ""
                st.markdown(
                    f'<div class="claim" style="border-left-color:{ui.PRIMARY_HOVER}">'
                    f'<div class="claim-meta">{ui._escape(item["lesson"])}'
                    f'<br><span style="color:{ui.INK_TERTIARY}">{item.get("kind", "")}{score}</span>'
                    "</div></div>",
                    unsafe_allow_html=True,
                )
        try:
            store = memory.get_store()
            lessons = memory.all_lessons(store, limit=100)
            saved = memory.previous_summaries(store, result.get("corpus_id", "")) if result.get("corpus_id") else []
        except Exception:  # noqa: BLE001
            lessons, saved = [], []
        with st.expander(f"All stored lessons ({len(lessons)})"):
            if lessons:
                st.dataframe(
                    [
                        {
                            "kind": item.get("kind"),
                            "seen": item.get("times_seen"),
                            "lesson": item.get("lesson"),
                            "updated": item.get("updated"),
                        }
                        for item in lessons
                    ],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption("No lessons yet. They appear after the first rejected claim.")
        with st.expander(f"Approved summaries saved for these papers ({len(saved)})"):
            for item in saved:
                st.markdown(f"**{item['saved']}** · {item['status']} · `{item['thread_id']}`")
                st.write(item["summary"])

    st.markdown(
        '<div class="section-title" style="margin-top:18px">RAG · Chroma retrievals</div>'
        '<div class="section-sub">Every search an agent made against the papers, with '
        "the passages that came back (lower distance = closer match).</div>",
        unsafe_allow_html=True,
    )
    index = result.get("rag_index") or {}
    if index:
        st.markdown(
            f'{ui.badge(index.get("collection", ""), ui.PRIMARY_HOVER)} '
            f'{ui.badge(str(index.get("chunks", 0)) + " chunks", ui.INK_SUBTLE)} '
            f'{ui.badge("reused" if index.get("reused") else "newly embedded", ui.SUCCESS)}',
            unsafe_allow_html=True,
        )
    retrievals = result.get("retrievals") or []
    if not retrievals:
        st.caption("No retrievals yet - run the workflow.")
    for item in retrievals:
        title = f"{item['agent']} · iteration {item['iteration']} · {len(item['hits'])} passages — {item['query'][:90]}"
        with st.expander(title):
            for hit in item["hits"]:
                st.markdown(
                    f"`{hit['source']}` · passage {hit['chunk'] + 1} · distance {hit['distance']}"
                )
                st.caption(hit["text"])


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

            if position + 1 < len(events):
                st.markdown('<div class="trace-connector">↓</div>', unsafe_allow_html=True)

        with st.expander("Raw final state (JSON)"):
            printable = {
                key: value
                for key, value in result.items()
                if key
                not in {"source_content", "source_documents", "trace", "messages", "retrievals"}
            }
            st.json(printable)


with tab_arch:
    st.markdown(
        '<div class="section-title">How the graph is built</div>'
        '<div class="section-sub">A supervisor graph: three agents, a human-approval '
        "step, a hop limit, two kinds of memory and a RAG index.</div>",
        unsafe_allow_html=True,
    )

    arch_left, arch_right = st.columns([1, 1.1], gap="large")

    with arch_left:
        components.html(ui.workflow_diagram(), height=ui.DIAGRAM_HEIGHT + 12, scrolling=False)

    with arch_right:
        explanations = [
            (
                "supervisor",
                "Supervisor (with a hop limit)",
                "Reads the state after every step and picks the next agent: no draft → "
                "summarizer; unchecked draft → fact checker; rejected → summarizer; "
                "verified → guard; guarded → human approval; approved → finalize. Each "
                "hand-off is a hop. At max_hops it routes to finalize and the run ends "
                "with HOP LIMIT REACHED.",
            ),
            (
                "summarizer",
                "Agent 1 · Summarizer",
                "Writes the summary with qwen2.5:3b from passages retrieved from Chroma. "
                "Before writing it recalls related lessons from long-term memory and "
                "reviewer notes from this thread. On a rewrite it also retrieves evidence "
                "for each rejected claim.",
            ),
            (
                "fact_checker",
                "Agent 2 · Fact checker",
                "Splits the draft into claims, retrieves the top-4 passages for each "
                "claim, and asks the model for a SUPPORTED / PARTIAL / UNSUPPORTED "
                "verdict. Every rejected claim is saved as a lesson.",
            ),
            (
                "guard",
                "Agent 3 · Guard",
                "Rule-based checks the LLM cannot argue with: absolute wording, numbers "
                "missing from the papers, chat preambles or file names, and length. "
                "If anything fails, the draft goes back to the summarizer.",
            ),
            (
                "human_review",
                "Human approval",
                "interrupt() pauses the graph and saves it to the SQLite checkpointer. "
                "Approve to finish, or send notes back. The run resumes on the same "
                "thread with Command(resume=...).",
            ),
            (
                "memory",
                "Memory and RAG",
                "Short-term: SqliteSaver checkpoints keyed by thread_id, plus a messages "
                "channel that grows across runs. Long-term: SqliteStore with "
                "nomic-embed-text semantic search over lessons and approved summaries. "
                "RAG: papers chunked and embedded into a Chroma collection.",
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
        '<div class="section-sub">From <code>graph.py</code>.</div>',
        unsafe_allow_html=True,
    )
    st.code(
        '''graph = StateGraph(ResearchState)

graph.add_node("read_source",   read_source)
graph.add_node("index_sources", index_sources)        # Chroma + nomic-embed-text
graph.add_node("supervisor",    supervisor)           # routing + hop limit
graph.add_node("summarizer",    summarizer_agent)
graph.add_node("fact_checker",  fact_checker_agent)
graph.add_node("guard",         guard_agent)
graph.add_node("human_review",  human_review)         # interrupt()
graph.add_node("finalize",      finalize)

graph.add_edge(START, "read_source")
graph.add_edge("read_source", "index_sources")
graph.add_edge("index_sources", "supervisor")

graph.add_conditional_edges("supervisor", route_from_supervisor, {
    "summarizer": "summarizer", "fact_checker": "fact_checker",
    "guard": "guard", "human_review": "human_review", "finalize": "finalize",
})
for agent in ("summarizer", "fact_checker", "guard", "human_review"):
    graph.add_edge(agent, "supervisor")      # every agent reports back
graph.add_edge("finalize", END)

app = graph.compile(
    checkpointer=SqliteSaver(...),   # short-term / thread memory
    store=SqliteStore(...),          # long-term memory
)''',
        language="python",
    )
