from __future__ import annotations


CANVAS = "#010102"
SURFACE_1 = "#0f1011"
SURFACE_2 = "#141516"
SURFACE_3 = "#18191a"
HAIRLINE = "#23252a"
HAIRLINE_STRONG = "#34343a"

PRIMARY = "#5e6ad2"
PRIMARY_HOVER = "#828fff"
PRIMARY_FOCUS = "#5e69d1"

INK = "#f7f8f8"
INK_MUTED = "#d0d6e0"
INK_SUBTLE = "#8a8f98"
INK_TERTIARY = "#62666d"

SUCCESS = "#27a644"
WARNING = "#d9a441"
DANGER = "#e05561"

STATUS_STYLES = {
    "SUPPORTED": (SUCCESS, "✓", "SUPPORTED"),
    "PARTIAL": (WARNING, "~", "PARTIAL"),
    "UNSUPPORTED": (DANGER, "✕", "UNSUPPORTED"),
}


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
  --canvas: {CANVAS};      --surface-1: {SURFACE_1};  --surface-2: {SURFACE_2};
  --surface-3: {SURFACE_3};--hairline: {HAIRLINE};    --hairline-strong: {HAIRLINE_STRONG};
  --primary: {PRIMARY};    --primary-hover: {PRIMARY_HOVER};
  --ink: {INK};            --ink-muted: {INK_MUTED};
  --ink-subtle: {INK_SUBTLE}; --ink-tertiary: {INK_TERTIARY};
  --success: {SUCCESS};    --warning: {WARNING};      --danger: {DANGER};
}}

/* ---- canvas ---------------------------------------------------------- */
.stApp, [data-testid="stAppViewContainer"] {{ background: var(--canvas); }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding: 1.6rem 2.4rem 4rem; max-width: 1320px; }}

html, body, [class*="css"], .stMarkdown, p, span, div, label {{
  font-family: 'Inter', -apple-system, system-ui, 'Segoe UI', sans-serif;
  color: var(--ink);
}}
code, pre, .stCode {{ font-family: 'JetBrains Mono', ui-monospace, monospace; }}

/* ---- sidebar --------------------------------------------------------- */
[data-testid="stSidebar"] {{
  background: var(--surface-1);
  border-right: 1px solid var(--hairline);
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.4rem; }}

/* ---- header ---------------------------------------------------------- */
.hero {{ padding: 8px 0 20px; border-bottom: 1px solid var(--hairline); margin-bottom: 22px; }}
.hero-eyebrow {{
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 500; letter-spacing: .4px;
  color: var(--ink-subtle); text-transform: uppercase; margin-bottom: 14px;
}}
.hero-dot {{
  width: 9px; height: 9px; border-radius: 9999px; background: var(--primary);
  box-shadow: 0 0 0 4px rgba(94,106,210,.18);
}}
.hero h1 {{
  font-size: 44px; font-weight: 600; line-height: 1.08; letter-spacing: -1.4px;
  margin: 0 0 10px; color: var(--ink);
}}
.hero p {{ font-size: 18px; line-height: 1.5; letter-spacing: -.1px; color: var(--ink-muted); margin: 0 0 16px; }}
.pipeline {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
.pipeline-step {{
  font-size: 12px; font-weight: 500; letter-spacing: .3px;
  padding: 4px 11px; border-radius: 9999px;
  background: var(--surface-2); border: 1px solid var(--hairline); color: var(--ink-muted);
}}
.pipeline-arrow {{ color: var(--ink-tertiary); font-size: 12px; }}

/* ---- metric strip ---------------------------------------------------- */
.metric {{
  background: var(--surface-1); border: 1px solid var(--hairline);
  border-radius: 12px; padding: 16px 18px; height: 100%;
}}
.metric-label {{
  font-size: 11px; font-weight: 500; letter-spacing: .5px; text-transform: uppercase;
  color: var(--ink-subtle); margin-bottom: 8px;
}}
.metric-value {{ font-size: 26px; font-weight: 600; letter-spacing: -.8px; line-height: 1.1; }}
.metric-sub {{ font-size: 12px; color: var(--ink-tertiary); margin-top: 6px; }}

/* ---- cards ----------------------------------------------------------- */
.card {{
  background: var(--surface-1); border: 1px solid var(--hairline);
  border-radius: 12px; padding: 20px 22px; margin-bottom: 14px;
}}
.card-accent {{ border-left: 2px solid var(--primary); }}
.card-title {{
  font-size: 15px; font-weight: 600; letter-spacing: -.2px;
  margin: 0 0 10px; display: flex; align-items: center; gap: 9px;
}}
.card-body {{ font-size: 15px; line-height: 1.62; color: var(--ink-muted); }}

/* ---- badges ---------------------------------------------------------- */
.badge {{
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; letter-spacing: .4px;
  padding: 3px 10px; border-radius: 9999px; white-space: nowrap;
}}

/* ---- claim rows ------------------------------------------------------ */
.claim {{
  background: var(--surface-1); border: 1px solid var(--hairline);
  border-radius: 12px; padding: 16px 18px; margin-bottom: 12px;
  border-left: 2px solid var(--hairline-strong);
}}
.claim-head {{ display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; margin-bottom: 9px; }}
.claim-no {{
  font-size: 11px; font-weight: 500; letter-spacing: .5px;
  color: var(--ink-tertiary); text-transform: uppercase;
}}
.claim-text {{ font-size: 15px; line-height: 1.55; color: var(--ink); margin: 0 0 10px; }}
.claim-meta {{ font-size: 13px; line-height: 1.55; color: var(--ink-subtle); }}
.claim-meta b {{ color: var(--ink-muted); font-weight: 500; }}
.claim-evidence {{
  margin-top: 10px; padding: 10px 12px; border-radius: 8px;
  background: var(--surface-2); border: 1px solid var(--hairline);
  font-size: 12.5px; line-height: 1.55; color: var(--ink-subtle); font-style: italic;
}}

/* ---- node timeline --------------------------------------------------- */
.tl-row {{
  display: flex; align-items: center; gap: 12px;
  padding: 11px 16px; margin-bottom: 8px; border-radius: 10px;
  background: var(--surface-1); border: 1px solid var(--hairline);
}}
.tl-glyph {{
  width: 22px; height: 22px; border-radius: 9999px; flex: 0 0 22px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
}}
.tl-name {{ font-size: 14px; font-weight: 500; letter-spacing: -.1px; flex: 1; }}
.tl-status {{ font-size: 11px; font-weight: 600; letter-spacing: .5px; }}

/* ---- highlighted summary text --------------------------------------- */
.summary-box {{
  background: var(--surface-1); border: 1px solid var(--hairline);
  border-radius: 12px; padding: 20px 22px;
  font-size: 15.5px; line-height: 1.72; color: var(--ink-muted);
}}
.hl-bad {{
  background: rgba(224,85,97,.14); border-bottom: 1.5px solid var(--danger);
  color: #ffd7da; padding: 1px 3px; border-radius: 3px;
}}
.hl-tag {{
  font-size: 10px; font-weight: 700; letter-spacing: .5px;
  color: var(--danger); vertical-align: super; margin-left: 3px;
}}

/* ---- trace ----------------------------------------------------------- */
.trace-block {{
  background: var(--surface-1); border: 1px solid var(--hairline);
  border-left: 2px solid var(--hairline-strong);
  border-radius: 12px; padding: 16px 18px; margin-bottom: 10px;
}}
.trace-head {{
  display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
  font-size: 13px; font-weight: 600; letter-spacing: .2px;
}}
.trace-step {{
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: var(--ink-tertiary); background: var(--surface-2);
  border: 1px solid var(--hairline); border-radius: 4px; padding: 1px 6px;
}}
.trace-body {{
  font-family: 'JetBrains Mono', monospace; font-size: 12.5px; line-height: 1.62;
  color: var(--ink-subtle); white-space: pre-wrap; margin: 0;
}}
.trace-connector {{ text-align: center; color: var(--ink-tertiary); font-size: 15px; margin: -2px 0 8px; }}

/* ---- streamlit widget restyle ---------------------------------------- */
.stButton > button {{
  background: var(--primary); color: #fff; border: none; border-radius: 8px;
  font-family: 'Inter', sans-serif; font-size: 14px; font-weight: 500;
  padding: 10px 14px; width: 100%; transition: background .15s ease;
}}
.stButton > button:hover {{ background: var(--primary-hover); color: #fff; }}
.stButton > button:focus {{ box-shadow: 0 0 0 2px rgba(94,105,209,.5); color: #fff; }}
.stButton > button:disabled {{ background: var(--surface-2); color: var(--ink-tertiary); }}

[data-testid="stSidebar"] .stButton > button {{ padding: 11px 14px; font-weight: 600; }}

.stTabs [data-baseweb="tab-list"] {{
  gap: 4px; border-bottom: 1px solid var(--hairline); background: transparent;
}}
.stTabs [data-baseweb="tab"] {{
  height: 40px; padding: 0 16px; background: transparent; border-radius: 8px 8px 0 0;
  font-size: 14px; font-weight: 500; color: var(--ink-subtle);
}}
.stTabs [aria-selected="true"] {{ color: var(--ink); background: var(--surface-1); }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--primary); }}

[data-testid="stExpander"] {{
  background: var(--surface-1); border: 1px solid var(--hairline);
  border-radius: 12px; margin-bottom: 10px;
}}
[data-testid="stExpander"] summary {{ font-size: 14px; font-weight: 500; color: var(--ink-muted); }}
[data-testid="stExpander"] summary:hover {{ color: var(--ink); }}

.stProgress > div > div > div > div {{ background: var(--primary); }}
.stProgress > div > div > div {{ background: var(--surface-2); }}

hr {{ border-color: var(--hairline); }}
[data-testid="stSidebar"] h3 {{
  font-size: 11px; font-weight: 600; letter-spacing: .6px; text-transform: uppercase;
  color: var(--ink-subtle); margin: 18px 0 10px;
}}
.side-file {{
  display: flex; align-items: center; gap: 9px;
  background: var(--surface-2); border: 1px solid var(--hairline);
  border-radius: 8px; padding: 8px 11px; margin-bottom: 6px;
  font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--ink-muted);
}}
.side-file .dot {{ width: 6px; height: 6px; border-radius: 9999px; background: var(--success); }}
.side-note {{ font-size: 12px; line-height: 1.5; color: var(--ink-tertiary); margin-top: 10px; }}

.section-title {{
  font-size: 20px; font-weight: 600; letter-spacing: -.4px;
  margin: 26px 0 4px; color: var(--ink);
}}
.section-sub {{ font-size: 13.5px; color: var(--ink-subtle); margin: 0 0 16px; }}
</style>
"""


def badge(text: str, color: str) -> str:
    """A pill badge tinted with `color`."""
    return (
        f'<span class="badge" style="background:{color}22;color:{color};'
        f'border:1px solid {color}44">{text}</span>'
    )


def metric(label: str, value: str, sub: str = "", color: str = INK) -> str:
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="color:{color}">{value}</div>{sub_html}</div>'
    )


def timeline_row(label: str, status: str) -> str:
    """One line of the live node timeline."""
    palette = {
        "completed": (SUCCESS, "✓", "COMPLETED"),
        "warning": (WARNING, "!", "ISSUE DETECTED"),
        "routing": (PRIMARY_HOVER, "↻", "LOOPING BACK"),
        "error": (DANGER, "✕", "FAILED"),
        "running": (PRIMARY_HOVER, "•", "RUNNING"),
    }
    color, glyph, text = palette.get(status, (INK_SUBTLE, "•", status.upper()))
    return (
        f'<div class="tl-row" style="border-left:2px solid {color}">'
        f'<div class="tl-glyph" style="background:{color}22;color:{color}">{glyph}</div>'
        f'<div class="tl-name">{label}</div>'
        f'<div class="tl-status" style="color:{color}">{text}</div></div>'
    )


def claim_card(claim: dict) -> str:
    """Render one claim-level fact-check verdict."""
    color, glyph, label = STATUS_STYLES.get(claim["status"], (INK_SUBTLE, "•", claim["status"]))
    evidence = ""
    if claim.get("evidence"):
        origin = f" — {claim['source_file']}" if claim.get("source_file") else ""
        evidence = (
            f'<div class="claim-evidence">Evidence from sources{origin}:<br>'
            f'“{_escape(claim["evidence"])}”</div>'
        )
    return (
        f'<div class="claim" style="border-left-color:{color}">'
        f'<div class="claim-head"><span class="claim-no">Claim {claim["id"]}</span>'
        f'{badge(f"{glyph} {label}", color)}</div>'
        f'<p class="claim-text">“{_escape(claim["text"])}”</p>'
        f'<div class="claim-meta"><b>Reason:</b> {_escape(claim["reason"])}</div>'
        f"{evidence}</div>"
    )


def highlight_unsupported(summary: str, unsupported: list[str]) -> str:
    """Wrap every unsupported sentence of the summary in a red warning style."""
    out = _escape(summary)
    for text in unsupported:
        safe = _escape(text)
        if safe in out:
            out = out.replace(
                safe,
                f'<span class="hl-bad">{safe}</span>'
                f'<span class="hl-tag">UNSUPPORTED</span>',
            )
    return out


def pre_text(text: str) -> str:
    """Escape `text` for a monospace block and keep its line breaks."""
    return _escape(text).replace("\r\n", "\n").replace("\n", "<br>")


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


VIEW_W, VIEW_H = 420, 516
DIAGRAM_HEIGHT = 600

_NODE_W, _NODE_H = 216, 54
_CX = 300


def _node(x: int, y: int, label: str, sub: str, state: str) -> str:
    """One box in the diagram. `state` is idle | active | done | failed."""
    fills = {
        "idle": (SURFACE_1, HAIRLINE, INK_SUBTLE),
        "active": (SURFACE_2, PRIMARY_HOVER, INK),
        "done": (SURFACE_1, SUCCESS, INK),
        "failed": (SURFACE_1, DANGER, INK),
    }
    fill, stroke, text_color = fills[state]
    pulse = (
        f'<animate attributeName="stroke-opacity" values="1;.35;1" dur="1.4s" '
        f'repeatCount="indefinite"/>'
        if state == "active"
        else ""
    )
    glow = (
        f'<rect x="{x - 4}" y="{y - 4}" width="{_NODE_W + 8}" height="{_NODE_H + 8}" rx="14" '
        f'fill="none" stroke="{PRIMARY}" stroke-opacity=".28" stroke-width="6"/>'
        if state == "active"
        else ""
    )
    sub_line = (
        f'<text x="{x + _NODE_W / 2}" y="{y + 38}" text-anchor="middle" '
        f'font-family="JetBrains Mono, monospace" font-size="10" fill="{INK_TERTIARY}">{sub}</text>'
        if sub
        else ""
    )
    dy = 24 if sub else 32
    return f"""
    {glow}
    <rect x="{x}" y="{y}" width="{_NODE_W}" height="{_NODE_H}" rx="10"
          fill="{fill}" stroke="{stroke}" stroke-width="1.5">{pulse}</rect>
    <text x="{x + _NODE_W / 2}" y="{y + dy}" text-anchor="middle"
          font-family="Inter, sans-serif" font-size="13" font-weight="600"
          letter-spacing="0.4" fill="{text_color}">{label}</text>
    {sub_line}"""


def _arrow(x: int, y1: int, y2: int, color: str, animated: bool = False) -> str:
    dash = (
        '<animate attributeName="stroke-dashoffset" values="12;0" dur=".7s" '
        'repeatCount="indefinite"/>'
        if animated
        else ""
    )
    style = 'stroke-dasharray="5 4"' if animated else ""
    return (
        f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2 - 8}" stroke="{color}" '
        f'stroke-width="1.6" {style} marker-end="url(#head-{color.lstrip("#")})">{dash}</line>'
    )


def workflow_diagram(
    node_states: dict[str, str] | None = None,
    loop_active: bool = False,
    verified: bool = False,
) -> str:
    """Build the SVG workflow diagram."""
    s = {
        "read_source": "idle",
        "summarize": "idle",
        "fact_check": "idle",
        "decision": "idle",
        "end": "idle",
        **(node_states or {}),
    }

    y_read, y_sum, y_fact, y_dec, y_end = 24, 128, 232, 336, 452
    line = HAIRLINE_STRONG
    loop_color = LOOP_LIVE if loop_active else LOOP_IDLE
    yes_color = SUCCESS if verified else HAIRLINE_STRONG

    loop_x = 118
    loop_path = (
        f"M {_CX - _NODE_W / 2} {y_dec + _NODE_H / 2} "
        f"H {loop_x + 14} Q {loop_x} {y_dec + _NODE_H / 2} {loop_x} {y_dec + _NODE_H / 2 - 14} "
        f"V {y_sum + _NODE_H / 2 + 14} Q {loop_x} {y_sum + _NODE_H / 2} {loop_x + 14} {y_sum + _NODE_H / 2} "
        f"H {_CX - _NODE_W / 2 - 8}"
    )
    loop_anim = (
        '<animate attributeName="stroke-dashoffset" values="16;0" dur=".55s" '
        'repeatCount="indefinite"/>'
        if loop_active
        else ""
    )
    loop_halo = (
        f'<path d="{loop_path}" fill="none" stroke="{PRIMARY}" stroke-opacity=".30" '
        f'stroke-width="11" stroke-linecap="round"/>'
        if loop_active
        else ""
    )
    loop_mid_y = y_sum + _NODE_H / 2 + 45
    loop_badge = (
        f'<rect x="{loop_x - 34}" y="{loop_mid_y - 11}" width="68" height="22" rx="11" '
        f'fill="{CANVAS}" stroke="{LOOP_LIVE}" stroke-width="1.5"/>'
        f'<text x="{loop_x}" y="{loop_mid_y + 4}" text-anchor="middle" '
        f'font-family="Inter,sans-serif" font-size="9.5" font-weight="700" '
        f'letter-spacing="0.6" fill="{LOOP_LIVE}">LOOP BACK</text>'
        if loop_active
        else ""
    )

    markers = "".join(
        f'<marker id="head-{c.lstrip("#")}" viewBox="0 0 10 10" refX="8" refY="5" '
        f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>'
        for c in {line, loop_color, yes_color, PRIMARY_HOVER, SUCCESS, LOOP_IDLE, LOOP_LIVE}
    )

    x = int(_CX - _NODE_W / 2)

    return f"""
<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>html,body{{margin:0;padding:0;background:{CANVAS};overflow:hidden;}}</style>
</head><body>
<svg viewBox="0 0 {VIEW_W} {VIEW_H}" preserveAspectRatio="xMidYMin meet"
     style="width:100%;max-width:470px;height:auto;display:block;margin:0 auto;"
     xmlns="http://www.w3.org/2000/svg">
  <defs>{markers}</defs>

  {_node(x, y_read, "READ SOURCES", "node 1 · processes uploaded research sources", s["read_source"])}
  {_arrow(_CX, y_read + _NODE_H, y_sum, line)}

  {_node(x, y_sum, "SUMMARIZE", "node 2 · qwen2.5:3b", s["summarize"])}
  {_arrow(_CX, y_sum + _NODE_H, y_fact, line)}

  {_node(x, y_fact, "FACT CHECK", "node 3 · claim by claim", s["fact_check"])}
  {_arrow(_CX, y_fact + _NODE_H, y_dec, line)}

  <!-- conditional router, drawn as a diamond-cornered box -->
  <rect x="{x + 18}" y="{y_dec}" width="{_NODE_W - 36}" height="{_NODE_H}" rx="26"
        fill="{SURFACE_2 if s['decision'] != 'idle' else SURFACE_1}"
        stroke="{PRIMARY if s['decision'] != 'idle' else HAIRLINE}" stroke-width="1.5"/>
  <text x="{_CX}" y="{y_dec + 24}" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="12.5" font-weight="600" letter-spacing="0.4"
        fill="{INK if s['decision'] != 'idle' else INK_SUBTLE}">ALL CLAIMS SUPPORTED?</text>
  <text x="{_CX}" y="{y_dec + 40}" text-anchor="middle" font-family="JetBrains Mono,monospace"
        font-size="10" fill="{INK_TERTIARY}">conditional edge</text>

  <!-- YES branch -> END -->
  {_arrow(_CX, y_dec + _NODE_H, y_end, yes_color)}
  <text x="{_CX + 12}" y="{y_dec + _NODE_H + 26}" font-family="Inter,sans-serif"
        font-size="11" font-weight="600" fill="{yes_color}">YES</text>

  <!-- NO branch -> back to SUMMARIZE : the conditional edge, the whole point -->
  {loop_halo}
  <path d="{loop_path}" fill="none" stroke="{loop_color}" stroke-width="{3.4 if loop_active else 2}"
        stroke-dasharray="8 6" marker-end="url(#head-{loop_color.lstrip('#')})">{loop_anim}</path>
  <rect x="{loop_x + 16}" y="{y_dec + _NODE_H / 2 - 24}" width="26" height="17" rx="8"
        fill="{loop_color}" fill-opacity="{0.9 if loop_active else 0.22}"
        stroke="{loop_color}" stroke-width="1"/>
  <text x="{loop_x + 29}" y="{y_dec + _NODE_H / 2 - 12}" text-anchor="middle"
        font-family="Inter,sans-serif" font-size="10" font-weight="700"
        fill="{CANVAS if loop_active else loop_color}">NO</text>
  {loop_badge}
  <text x="8" y="{(y_sum + y_dec) / 2 + 26}" font-family="Inter,sans-serif"
        font-size="10.5" font-weight="700" fill="{loop_color}">
        SELF-CORRECTION</text>
  <text x="8" y="{(y_sum + y_dec) / 2 + 40}" font-family="Inter,sans-serif"
        font-size="10.5" font-weight="700" fill="{loop_color}">LOOP</text>
  <text x="8" y="{(y_sum + y_dec) / 2 + 56}" font-family="JetBrains Mono,monospace"
        font-size="9" fill="{INK_TERTIARY}">feedback →</text>
  <text x="8" y="{(y_sum + y_dec) / 2 + 68}" font-family="JetBrains Mono,monospace"
        font-size="9" fill="{INK_TERTIARY}">summarize</text>

  <!-- END -->
  <rect x="{x + 58}" y="{y_end}" width="{_NODE_W - 116}" height="44" rx="22"
        fill="{SURFACE_1}" stroke="{SUCCESS if s['end'] == 'done' else HAIRLINE}" stroke-width="1.5"/>
  <text x="{_CX}" y="{y_end + 28}" text-anchor="middle" font-family="Inter,sans-serif"
        font-size="13" font-weight="600" letter-spacing="0.6"
        fill="{SUCCESS if s['end'] == 'done' else INK_SUBTLE}">END</text>
</svg>
</body></html>"""


LOOP_IDLE = "#3f4372"
LOOP_LIVE = PRIMARY_HOVER

EXTRA_CSS = f"""
<style>
/* ---- research input panel (step 1) ----------------------------------- */
.panel {{
  background: var(--surface-1); border: 1px solid var(--hairline);
  border-radius: 12px; padding: 18px 20px 6px; margin-bottom: 6px;
}}
.panel-head {{
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-bottom: 4px;
}}
.step-chip {{
  font-size: 11px; font-weight: 600; letter-spacing: .5px;
  padding: 3px 9px; border-radius: 9999px;
  background: rgba(94,106,210,.16); color: {PRIMARY_HOVER};
  border: 1px solid rgba(94,106,210,.34);
}}
.panel-title {{ font-size: 17px; font-weight: 600; letter-spacing: -.3px; color: var(--ink); }}
.panel-note {{ font-size: 12.5px; color: var(--ink-tertiary); margin: 2px 0 12px; }}

.src-tile {{
  background: var(--surface-2); border: 1px solid var(--hairline);
  border-radius: 10px; padding: 12px 14px; height: 100%;
}}
.src-tile.on {{ border-color: rgba(94,106,210,.45); }}
.src-name {{
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: var(--ink); display: flex; align-items: center; gap: 7px; margin-bottom: 6px;
}}
.src-title {{ font-size: 13px; line-height: 1.45; color: var(--ink-muted); margin-bottom: 8px; }}
.src-meta {{ font-size: 11px; color: var(--ink-tertiary); font-family: 'JetBrains Mono', monospace; }}

/* ---- journey stepper -------------------------------------------------- */
.journey {{
  display: flex; align-items: stretch; gap: 6px; flex-wrap: nowrap;
  overflow-x: auto; padding: 4px 0 2px; margin-bottom: 4px;
}}
.jstep {{
  flex: 1 1 0; min-width: 118px; min-height: 64px;
  display: flex; flex-direction: column; justify-content: space-between;
  background: var(--surface-1); border: 1px solid var(--hairline);
  border-radius: 10px; padding: 10px 11px; position: relative;
}}
.jstep-top {{
  display: flex; align-items: center; gap: 7px; margin-bottom: 5px;
}}
.jstep-num {{
  width: 18px; height: 18px; border-radius: 9999px; flex: 0 0 18px;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700;
}}
.jstep-label {{
  font-size: 12px; font-weight: 500; line-height: 1.3; letter-spacing: -.1px;
}}
.jstep-state {{
  font-size: 9.5px; font-weight: 600; letter-spacing: .5px; text-transform: uppercase;
}}
.jstep.loopstep {{ border-style: dashed; }}

@keyframes jpulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .45; }} }}
.jstep.active {{ animation: jpulse 1.5s ease-in-out infinite; }}

/* ---- conditional routing banner --------------------------------------- */
.routing {{
  border: 1.5px dashed {PRIMARY_HOVER};
  background: linear-gradient(90deg, rgba(94,106,210,.20), rgba(94,106,210,.06));
  border-radius: 12px; padding: 18px 22px; margin: 6px 0 18px;
}}
.routing-head {{
  display: flex; align-items: center; gap: 11px; flex-wrap: wrap; margin-bottom: 10px;
}}
.routing-glyph {{
  width: 30px; height: 30px; border-radius: 9999px; flex: 0 0 30px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(94,106,210,.26); color: {PRIMARY_HOVER};
  font-size: 15px; font-weight: 700;
}}
.routing-title {{
  font-size: 16px; font-weight: 600; letter-spacing: -.3px; color: {PRIMARY_HOVER};
}}
.routing-edge {{
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  background: var(--canvas); border: 1px solid rgba(94,106,210,.4);
  border-radius: 6px; padding: 3px 9px; color: var(--ink-muted);
}}
.routing-body {{ font-size: 14px; line-height: 1.6; color: var(--ink-muted); }}
.routing-claim {{
  margin-top: 10px; padding: 10px 13px; border-radius: 8px;
  background: rgba(224,85,97,.12); border-left: 2px solid var(--danger);
  font-size: 13.5px; line-height: 1.55; color: #ffd7da;
}}

@keyframes routeflash {{ 0%,100% {{ border-color: {PRIMARY_HOVER}; }} 50% {{ border-color: rgba(94,106,210,.3); }} }}
.routing.live {{ animation: routeflash 1.1s ease-in-out infinite; }}
</style>
"""


JOURNEY = [
    ("Read Sources", "read"),
    ("Run Autonomous Research", "run"),
    ("Summarize", "summarize"),
    ("Fact Check", "factcheck"),
    ("Automatic Loop", "loop"),
    ("Corrected Summary", "corrected"),
    ("Verified", "verified"),
]

_JOURNEY_STYLE = {
    "done": (SUCCESS, "✓", "done"),
    "active": (PRIMARY_HOVER, "•", "running"),
    "pending": (INK_TERTIARY, "", "pending"),
    "skipped": (INK_TERTIARY, "–", "not needed"),
    "failed": (DANGER, "✕", "failed"),
}


def journey_status(state: dict | None, finished: bool = False) -> dict[str, str]:
    """Work out where the run is along the seven-stage journey."""
    status = {key: "pending" for _, key in JOURNEY}
    if not state:
        return status

    summaries = state.get("summary_history", []) or []
    checks = state.get("claims_history", []) or []
    verified = bool(state.get("is_verified"))
    looped = len(summaries) >= 2

    if state.get("sources"):
        status["read"] = "done"
        status["run"] = "done"
    if summaries:
        status["summarize"] = "done"
    if checks:
        status["factcheck"] = "done"
    if looped:
        status["loop"] = "done"
        status["corrected"] = "done"
    if verified:
        status["verified"] = "done"

    if finished:
        if not looped and verified:
            status["loop"] = "skipped"
            status["corrected"] = "skipped"
        if not verified:
            status["verified"] = "failed"
        return status

    for _, key in JOURNEY:
        if status[key] == "pending":
            status[key] = "active"
            break
    return status


def journey_stepper(status: dict[str, str]) -> str:
    """Render the seven-stage journey as a horizontal stepper."""
    cells = []
    for index, (label, key) in enumerate(JOURNEY, start=1):
        state = status.get(key, "pending")
        color, glyph, caption = _JOURNEY_STYLE[state]
        classes = "jstep"
        if key == "loop":
            classes += " loopstep"
        if state == "active":
            classes += " active"
        border = (
            f"border-color:{color}66;" if state in {"done", "active", "failed"} else ""
        )
        cells.append(
            f'<div class="{classes}" style="{border}">'
            f'<div class="jstep-top">'
            f'<div class="jstep-num" style="background:{color}22;color:{color}">'
            f"{glyph or index}</div>"
            f'<div class="jstep-label" style="color:'
            f'{INK if state in {"done", "active", "failed"} else INK_TERTIARY}">{label}</div>'
            f"</div>"
            f'<div class="jstep-state" style="color:{color}">{caption}</div>'
            f"</div>"
        )
    return f'<div class="journey">{"".join(cells)}</div>'


def routing_banner(iteration: int, rejected_claim: str = "", live: bool = False) -> str:
    """The moment the conditional edge sends the run back to summarize."""
    claim = (
        f'<div class="routing-claim">Rejected claim: “{_escape(rejected_claim)}”</div>'
        if rejected_claim
        else ""
    )
    verb = "is routing" if live else "routed"
    return (
        f'<div class="routing{" live" if live else ""}">'
        f'<div class="routing-head">'
        f'<div class="routing-glyph">↻</div>'
        f'<div class="routing-title">Conditional edge fired — looping back</div>'
        f'<div class="routing-edge">fact_check → summarize</div>'
        f"</div>"
        f'<div class="routing-body">The fact checker rejected the summary from '
        f"iteration {iteration}, so <b>route_after_fact_check()</b> returned "
        f'<b>"summarize"</b> and LangGraph {verb} execution <b>backwards</b> to '
        f"node 2 — carrying the written feedback along in the graph state. "
        f"This edge is the self-correction loop.</div>"
        f"{claim}</div>"
    )


def source_tile(doc: dict, selected: bool = True) -> str:
    """One source document shown in the prominent research-input panel."""
    title = doc["content"].splitlines()[0].replace("TITLE:", "").strip()
    dot = SUCCESS if selected else INK_TERTIARY
    return (
        f'<div class="src-tile{" on" if selected else ""}">'
        f'<div class="src-name">'
        f'<span style="width:6px;height:6px;border-radius:9999px;background:{dot};'
        f'display:inline-block"></span>{_escape(doc["name"])}</div>'
        f'<div class="src-title">{_escape(title)}</div>'
        f'<div class="src-meta">{doc["words"]} words</div>'
        f"</div>"
    )


FINAL_CSS = """
<style>
  .verdict-wrap { margin: 6px 0 22px; }
  .verdict-card {
    border: 1px solid #34343a; border-radius: 10px; overflow: hidden;
    background: linear-gradient(180deg, #0d0f13 0%, #0a0b0e 100%);
  }
  .verdict-top {
    padding: 22px 26px 18px; text-align: center;
    border-bottom: 1px solid #23252a;
  }
  .verdict-eyebrow {
    font-size: 10px; letter-spacing: .18em; text-transform: uppercase;
    color: #8a8f98; margin-bottom: 12px; font-weight: 600;
  }
  .verdict-stamp {
    display: inline-flex; align-items: center; gap: 10px;
    font-size: 27px; font-weight: 700; letter-spacing: -0.01em;
  }
  .verdict-stats {
    display: grid; grid-template-columns: repeat(4, 1fr);
    border-bottom: 1px solid #23252a;
  }
  .verdict-stat { padding: 15px 18px; text-align: center; border-right: 1px solid #23252a; }
  .verdict-stat:last-child { border-right: none; }
  .verdict-stat .v { font-size: 21px; font-weight: 650; color: #f7f8f8; line-height: 1.2; }
  .verdict-stat .l {
    font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
    color: #8a8f98; margin-top: 5px; font-weight: 600;
  }
  .verdict-body { padding: 20px 26px 22px; }
  .verdict-label {
    font-size: 10px; letter-spacing: .16em; text-transform: uppercase;
    color: #8a8f98; font-weight: 600; margin-bottom: 10px;
  }
  .verdict-summary {
    font-size: 15px; line-height: 1.75; color: #f7f8f8;
    border-left: 2px solid #27a644; padding: 4px 0 4px 16px;
  }
  .verdict-correction {
    margin-top: 20px; padding-top: 18px; border-top: 1px solid #23252a;
  }
  .verdict-claim {
    font-size: 13.5px; line-height: 1.6; color: #d0d6e0;
    background: #16090b; border-left: 2px solid #e05561;
    padding: 10px 14px; border-radius: 0 5px 5px 0; margin-bottom: 10px;
  }
  .verdict-reason { font-size: 13px; line-height: 1.65; color: #8a8f98; }
  .verdict-fixed {
    margin-top: 10px; font-size: 13px; color: #27a644; font-weight: 600;
  }
  .verdict-flow {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
    padding: 14px 26px; border-top: 1px solid #23252a; background: #08090b;
  }
  .flow-step {
    font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase;
    font-weight: 600; color: #8a8f98; border: 1px solid #23252a;
    border-radius: 5px; padding: 5px 10px; white-space: nowrap;
  }
  .flow-step.final { color: #27a644; border-color: #27a644; }
  .flow-arrow { color: #62666d; font-size: 12px; }
  @media (max-width: 760px) {
    .verdict-stats { grid-template-columns: repeat(2, 1fr); }
    .verdict-stat { border-bottom: 1px solid #23252a; }
  }
</style>
"""

_FLOW = [
    "Uploaded Papers",
    "Initial Summary",
    "Fact Check",
    "Correction Loop",
]


def final_result_panel(
    state: dict,
    source_count: int,
    rejected_claim: str = "",
    rejected_reason: str = "",
) -> str:
    """The headline answer: what the run concluded, and what backs it."""
    verified = bool(state.get("is_verified"))
    iterations = int(state.get("iteration", 0) or 0)
    loops = max(0, iterations - 1)
    claims = state.get("claims", []) or []
    supported = sum(1 for c in claims if c["status"] == "SUPPORTED")
    summary = state.get("summary", "") or ""

    colour = SUCCESS if verified else WARNING
    stamp = "✅ VERIFIED" if verified else "⚠ UNVERIFIED"
    summary_label = "Final verified summary" if verified else "Final summary (unverified)"

    stats = [
        (str(source_count), "Sources analyzed"),
        (str(iterations), "Iterations"),
        (str(loops), "Correction loops"),
        (f"{supported}/{len(claims)}" if claims else "—", "Claims verified"),
    ]
    stat_html = "".join(
        f'<div class="verdict-stat"><div class="v">{_escape(value)}</div>'
        f'<div class="l">{_escape(label)}</div></div>'
        for value, label in stats
    )

    correction = ""
    if rejected_claim:
        reason = rejected_reason or (
            "The uploaded sources do not support this claim as stated."
        )
        correction = (
            '<div class="verdict-correction">'
            '<div class="verdict-label">Correction detected</div>'
            f'<div class="verdict-claim">✕ &ldquo;{_escape(rejected_claim)}&rdquo;</div>'
            f'<div class="verdict-reason"><b>Reason:</b> {_escape(reason)}</div>'
            f'<div class="verdict-fixed">→ Corrected and verified in iteration {iterations}.</div>'
            "</div>"
        )

    steps = list(_FLOW)
    if not loops:
        steps.remove("Correction Loop")
    flow_html = f'<span class="flow-arrow">→</span>'.join(
        f'<span class="flow-step">{_escape(step)}</span>' for step in steps
    )
    flow_html += (
        '<span class="flow-arrow">→</span>'
        f'<span class="flow-step final">{_escape(summary_label)}</span>'
    )

    return (
        '<div class="verdict-wrap"><div class="verdict-card">'
        '<div class="verdict-top">'
        '<div class="verdict-eyebrow">Final verdict</div>'
        f'<div class="verdict-stamp" style="color:{colour}">{stamp}</div>'
        "</div>"
        f'<div class="verdict-stats">{stat_html}</div>'
        '<div class="verdict-body">'
        f'<div class="verdict-label">{_escape(summary_label)}</div>'
        f'<div class="verdict-summary" style="border-left-color:{colour}">'
        f"{_escape(summary)}</div>"
        f"{correction}"
        "</div>"
        f'<div class="verdict-flow">{flow_html}</div>'
        "</div></div>"
    )


TOOLBAR_CSS = """
<style>
  [data-testid="stDeployButton"],
  .stDeployButton,
  [data-testid="stMainMenu"],
  #MainMenu,
  [data-testid="stAppDeployButton"],
  [data-testid="stDecoration"],
  footer { display: none !important; }

  /* The toolbar box itself would leave a gap once its buttons are gone. */
  [data-testid="stToolbar"] { right: 0.5rem; }
  [data-testid="stToolbarActions"] { display: none !important; }

  /* Keep the spinner: a long fact-check pass must not look frozen. */
  [data-testid="stStatusWidget"] { display: flex !important; }
</style>
"""
