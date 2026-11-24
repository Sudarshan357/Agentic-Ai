# Multi-Step Research Summarizer Graph

An autonomous **LangGraph** workflow that reads local research documents, writes a
summary with a local LLM, **fact-checks its own summary against the sources**, and
automatically **loops back to rewrite** any claim the sources do not support.

Everything runs locally through [Ollama](https://ollama.com) with the
`qwen2.5:3b` model. **No paid APIs and no API keys are required.**

---

## 1. Project Overview

Large language models overstate things. A summarizer given a source that says
*"electric vehicles produce zero tailpipe emissions"* will happily write *"electric
vehicles have zero environmental impact"* — a claim the sources actively contradict,
because they also describe battery-manufacturing emissions and the effect of the
electricity mix.

This project does not simply hope the model behaves. It builds a **graph** in which a
second node audits the first node's output, and a **conditional edge** sends the work
back for revision when the audit fails. The system keeps looping until every claim is
supported, or until a safety limit stops it.

The user uploads 2 or 3 research papers (PDF or TXT). Those uploaded files are
the only research input: there is no topic field, no question box, and no web
search anywhere in the workflow.

---

## 2. Architecture

The workflow is a **supervisor graph**. A supervisor node routes the work between
three agents, each with one job, and a human-approval step. Every agent reports
back to the supervisor, which picks who goes next.

```
 START -> read_source -> index_sources (RAG) -> SUPERVISOR  <--+
                                                  |           |
              +------------+--------------+-------+------+    |
              v            v              v              v    |
         summarizer   fact_checker      guard      human_review
              |            |              |              |    |
              +------------+--------------+--------------+----+
                                                  |
                                     supervisor -> finalize -> END
```

| Part | Role |
|---|---|
| **supervisor** | Rule-based router. No draft → summarizer · unchecked draft → fact_checker · rejected → summarizer · verified → guard · guarded → human_review · approved → finalize. Each hand-off is one **hop**; at `max_hops` it goes straight to finalize (`HOP LIMIT REACHED`). |
| **summarizer** (agent) | Writes and rewrites the summary with `qwen2.5:3b` from passages retrieved from Chroma. Before writing, it recalls related lessons from long-term memory and reviewer notes from the thread. |
| **fact_checker** (agent) | Splits the draft into claims, retrieves the top-4 passages for **each claim**, and asks for a SUPPORTED / PARTIAL / UNSUPPORTED verdict. Rejected claims are saved as lessons. |
| **guard** (agent) | Rule-based safety checks: absolute wording, numbers that don't appear in the papers, chat preambles or file names, and length. |
| **human_review** | `interrupt()` pauses the graph. The UI shows Approve / Request changes, and the run resumes on the same thread with `Command(resume=...)`. |

### Memory and RAG

| Layer | Implementation | What it holds |
|---|---|---|
| Short-term (thread) memory | `SqliteSaver` checkpointer → `memory_data/checkpoints.sqlite`, keyed by `thread_id` | Full graph state after every step, so a paused run can resume. The `messages` channel (an `add_messages` reducer) grows across runs on the same thread, and the summarizer reads earlier reviewer notes from it. |
| Long-term memory | `SqliteStore` → `memory_data/store.sqlite`, with semantic search via `nomic-embed-text` | `("lessons",)`: mistakes caught by the fact checker, the guard or the reviewer. `("summaries", corpus_id)`: approved summaries. |
| RAG | Chroma (`memory_data/chroma/`) + `OllamaEmbeddings("nomic-embed-text")` | The papers, split into ~120-word chunks. One collection per set of papers, reused if the same files are uploaded again. |

The sidebar has the hop limit, the approval toggle, the current thread (plus
**Start a new thread**), and a button to clear long-term memory. The
**Memory & RAG** tab shows the thread's messages, the stored lessons, and every
retrieval each agent made.

---

## 3. Installation

### Prerequisites

* **Python 3.10 or newer** (developed on 3.13)
* **Ollama** — download from <https://ollama.com/download>

### Steps

```bash
# 1. install the Python dependencies
pip install -r requirements.txt

# 2. make sure the Ollama service is running
ollama serve

# 3. pull the model (about 1.9 GB, one time only)
ollama pull qwen2.5:3b
ollama pull nomic-embed-text   # embeddings for RAG and long-term memory

# 4. run the application
streamlit run app.py
```

The app opens at <http://localhost:8501>.

> **Windows note.** If `pip` tries to compile a package from source and fails
> (an "Application Control policy has blocked this file" error, for example),
> force prebuilt wheels:
>
> ```bash
> pip install --only-binary=:all: -r requirements.txt
> ```

> **Note on `ollama serve`.** On Windows and macOS the Ollama desktop app usually
> starts the service automatically, and `ollama serve` will then report that the
> address is already in use. That message is harmless — it means the service is
> already up. The sidebar shows **Ollama online** when the app can reach it.

### Verify the backend before presenting

```bash
python test_workflow.py     # runs the graph, prints the full trace, asserts 10 behaviours
python test_ui.py           # renders the Streamlit app headlessly and clicks RUN
```

---

## 4. Project Structure

```
multi_step_research_summarizer/
│
├── app.py               Streamlit UI (layout and orchestration only)
├── ui.py                design tokens, CSS, and the animated SVG diagram
├── graph.py             the LangGraph StateGraph - nodes, edges, conditional edge
├── nodes.py             supervisor, summarizer / fact_checker / guard agents,
│                        human_review (interrupt), finalize
├── memory.py            SqliteSaver (thread memory) + SqliteStore (long-term)
├── rag.py               Chroma + nomic-embed-text indexing and retrieval
├── state.py             the ResearchState TypedDict
├── prompts.py           all LLM prompt templates
│
├── test_workflow.py     backend test - guard unit tests + full graph run
├── test_ui.py           headless Streamlit test
│
├── requirements.txt
├── README.md
├── DESIGN.md            the Linear-inspired design system the UI follows
│
├── .streamlit/
│   └── config.toml      base dark theme
│
├── sources/
│   └── (sample papers; the app reads whatever the user uploads instead)
│
└── screenshots/
```

`ui.py` is separate from `app.py` on purpose: it keeps all the styling out of the
application file so `app.py` stays short enough to read on a projector.

---

## 5. Demo Flow

With **Demonstrate correction loop** enabled (the default), pressing
**RUN AUTONOMOUS WORKFLOW** produces this every time:

| Step | Node | What happens |
|---|---|---|
| 1 | `read_source` | Loads the uploaded PDF/TXT papers into the state. This is the only ground truth. |
| 2 | `summarize` — iteration 1 | qwen2.5:3b writes a summary. One deliberate over-claim is appended (see below). |
| 3 | `fact_check` | Splits the summary into sentence-level claims and judges each against the sources. The over-claim comes back **UNSUPPORTED**. |
| 4 | **conditional router** | `route_after_fact_check` sees `unsupported_claims` is non-empty and returns `"summarize"`. The diagram lights up the loop-back edge. |
| 5 | `summarize` — iteration 2 | The summarizer now receives the fact-check feedback and rewrites. |
| 6 | `fact_check` | All claims supported. `is_verified` becomes `True`. |
| 7 | `finalize` → `END` | The router returns `"finish"` and the graph stops. |

Typical runtime: **35–50 seconds** on CPU.

### Why demo mode exists

A 3-billion-parameter model does not hallucinate on cue. If the demonstration
waited for a spontaneous error, the correction loop might never fire in front of an
audience. So with demo mode ON, the `summarize` node appends **one** documented
over-claim to the **first** summary only:

> *"Overall, electric vehicles have zero environmental impact and are completely
> clean from production to disposal."*

Everything after that point is genuine:

* the fact checker is **not** told the sentence was injected — it evaluates it like any other claim;
* the router reacts to the real verdict;
* iteration 2 onwards contains no injected text;
* switching demo mode OFF runs the pipeline completely untouched.

The injection lives in `prompts.py` (`DEMO_OVERCLAIM`) and is applied in
`nodes.py::summarize`, both with comments explaining why.

### How the fact checker works

For each claim the node does two things:

1. **Asks the LLM to judge it** against the full source text, returning JSON with a
   status (`SUPPORTED` / `PARTIAL` / `UNSUPPORTED`), a reason, and the evidence
   sentence it relied on. This is the real fact check and it runs on every claim.
2. **Applies a deterministic over-claim guard.** The sources qualify every
   environmental statement, so absolute phrasing ("zero environmental impact",
   "completely clean", "zero emissions" without *tailpipe*) is an over-claim by
   construction. This guarantees the demonstration cannot silently pass a claim the
   sources plainly contradict.

The guard is **negation-aware**: *"EVs do **not** have zero environmental impact"* is
a correct sentence and is deliberately **not** flagged. Without that check, a good
revision would be rejected and the graph would loop until the safeguard fired.
`test_workflow.py` pins this behaviour down with unit tests.

### The safeguard

`max_iterations` (default 3, adjustable in the sidebar) caps the number of
summaries. If the summary still fails after the last attempt, the router returns
`"finish"` anyway and `finalize` reports **VERIFICATION FAILED** instead of looping
forever. You can watch this by setting the slider to 1.

---

## 6. The User Interface

Five tabs, styled after the Linear design system (see `DESIGN.md`):

| Tab | Contents |
|---|---|
| **Workflow** | Live graph diagram with the active node pulsing, the node timeline, and the before/after summary comparison with unsupported claims highlighted in red. |
| **Sources** | The three research documents, expandable for inspection. |
| **Fact Check** | Claim-by-claim verdicts for every iteration, with reasons and the evidence sentence. |
| **Full Trace** | The complete execution trace, including the `CONDITIONAL ROUTING ACTIVATED` block, plus the raw final state as JSON. |
| **Architecture** | The graph diagram, a plain-language explanation of each node, and the actual `graph.py` code. |

---

## 7. Key Concepts Demonstrated

* **Autonomous workflow** — one button press runs the whole thing with no human in the loop.
* **Multi-node graph** — four nodes wired with explicit edges via `StateGraph`.
* **State management** — a typed `ResearchState` carries everything between nodes.
* **Conditional routing** — `add_conditional_edges` picks the next node at runtime.
* **Feedback loops** — a genuine cycle in the graph, `fact_check` → `summarize`.
* **Self-correction** — the rewrite is driven by the critic's written feedback.
* **Fact verification** — claim-level checking against source text, with evidence.
* **Hallucination reduction** — unsupported claims are caught before the user sees them.
* **Loop safety** — a hard iteration cap prevents infinite cycles.

---

## 8. Jury Demonstration Script

> "I give the system three research sources. The first node reads them into the graph
> state. The summarization node generates a summary — but that first summary contains
> an unsupported claim. Instead of accepting it, the next node fact-checks every
> important claim against the original source material, and it detects the
> unsupported one. The LangGraph conditional edge then automatically routes the
> workflow back to the summarization node. The summarizer receives the feedback and
> generates a corrected version. The fact checker verifies the corrected version, and
> only then does the workflow end."

Open the **Workflow** tab while it runs — the loop-back edge lights up at step 4 —
then the **Full Trace** tab to show the same story in text, and the **Architecture**
tab to show that it is a real `StateGraph` with a real conditional edge.
