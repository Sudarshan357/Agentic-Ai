# UI Theme Guide: Linear-style dark dashboard

Build the UI in this style. It is a near-black, Linear-inspired dark theme for
technical tools and dashboards. It should feel dense, precise and calm. Hierarchy
comes from **stacked surfaces and 1px hairline borders, not shadows or gradients**.
One lavender-blue accent is used sparingly. Status colors (green / amber / red)
appear only where they carry meaning.

---

## 1. Design principles

1. **Dark only.** The canvas is `#010102`, near-black with a faint blue tint. Never use pure `#000`, and never ship a light mode.
2. **One accent.** Lavender `#5e6ad2` is reserved for primary buttons, focus rings, active states, the brand dot, and "currently running" highlights. Never use it as a large fill or section background.
3. **Depth from surfaces.** Each layer steps up a grey: canvas → surface-1 → surface-2 → surface-3. Cards are surface-1 with a 1px hairline border. Hovered, nested or selected items move up one step. No drop shadows.
4. **Semantic color has meaning.** Green = passed/done, amber = warning/waiting, red = failed/rejected. Use them for badges, left-border stripes and status text, not decoration.
5. **Text hierarchy through grey levels.** Use four text greys (ink → muted → subtle → tertiary) instead of many font sizes.
6. **Tight type.** Headings use negative letter-spacing. Small uppercase labels use positive letter-spacing.
7. **Show the system working.** State is always visible: progress, live timelines, pulsing active items and step-by-step traces.

---

## 2. Color tokens

```css
:root {
  /* surfaces (dark -> lighter) */
  --canvas:          #010102;  /* page background */
  --surface-1:       #0f1011;  /* cards, sidebar, panels */
  --surface-2:       #141516;  /* nested items, hovered/selected, chips */
  --surface-3:       #18191a;  /* dropdowns, deepest lift */

  /* borders */
  --hairline:        #23252a;  /* default 1px border / divider */
  --hairline-strong: #34343a;  /* emphasized border, idle left-stripes */

  /* accent (use sparingly) */
  --primary:         #5e6ad2;  /* primary button, active tab underline, progress */
  --primary-hover:   #828fff;  /* hover, "running/active" text and outlines */
  --primary-focus:   #5e69d1;  /* focus ring (2px at 50% opacity) */

  /* text */
  --ink:             #f7f8f8;  /* headings, key values */
  --ink-muted:       #d0d6e0;  /* body text inside cards */
  --ink-subtle:      #8a8f98;  /* labels, secondary text, inactive tabs */
  --ink-tertiary:    #62666d;  /* footnotes, disabled, hints */

  /* semantic */
  --success:         #27a644;
  --warning:         #d9a441;
  --danger:          #e05561;
}
```

**Tints.** For a colored badge or chip, use the color itself for the text, the color at ~13% alpha for the background, and ~27% alpha for the border. In hex that is `color + "22"` for the background and `color + "44"` for the border. Example: `background: #27a64422; color: #27a644; border: 1px solid #27a64444`.

Translucent accent values that are used often:
- Accent chip background: `rgba(94,106,210,.16)` with border `rgba(94,106,210,.34)`
- Brand dot halo: `box-shadow: 0 0 0 4px rgba(94,106,210,.18)`
- Error highlight on text: `background: rgba(224,85,97,.14); border-bottom: 1.5px solid var(--danger); color: #ffd7da`

---

## 3. Typography

- **Sans:** `Inter` (400/500/600/700), with fallback `-apple-system, system-ui, 'Segoe UI', sans-serif`
- **Mono:** `JetBrains Mono` (400/500). Use it for IDs, file names, code, log/trace output and technical tags.
- Google Fonts import:
  `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap`

| Role | Size | Weight | Letter-spacing | Color |
|---|---|---|---|---|
| Page title (h1) | 44px, line-height 1.08 | 600 | -1.4px | ink |
| Hero subtitle | 18px, lh 1.5 | 400 | -0.1px | ink-muted |
| Section title | 20px | 600 | -0.4px | ink |
| Section subtitle | 13.5px | 400 | 0 | ink-subtle |
| Panel title | 17px | 600 | -0.3px | ink |
| Card title | 15px | 600 | -0.2px | ink |
| Card body | 15px, lh 1.6 | 400 | 0 | ink-muted |
| Metric value | 26px, lh 1.1 | 600 | -0.8px | status color or ink |
| Eyebrow / label | 11–13px, UPPERCASE | 500–600 | +0.4 to +0.6px | ink-subtle |
| Badge text | 11px | 600 | +0.4px | the badge's color |
| Mono log text | 12.5px, lh 1.62 | 400 | 0 | ink-subtle |
| Footnote | 12px | 400 | 0 | ink-tertiary |

Rule: big text gets **negative** tracking, and tiny uppercase labels get **positive** tracking.

---

## 4. Spacing, radius, layout

- **Base unit 4px.** Steps: 4 · 8 · 12 · 16 · 24 · 32 · 48.
- **Radius:** 4px (tiny tags, step numbers) · 6–8px (buttons, inputs, inner boxes) · 10px (list rows, small tiles) · **12px (cards, the default)** · 9999px (pills, badges, dots).
- **Card padding:** 16–22px. **Gap between cards:** 10–14px.
- **Content width:** max ~1320px, page padding `1.6rem 2.4rem 4rem`.
- **Layouts:** a sidebar for controls, then the main column: hero → stepper → metric strip (4-up) → tabs → content, with two-column splits inside tabs (e.g. diagram | timeline).
- **Responsive:** grids go 4 → 2 columns below ~760px. Horizontal steppers scroll sideways rather than wrapping.

---

## 5. Components

### Hero header
```css
.hero { padding: 8px 0 20px; border-bottom: 1px solid var(--hairline); margin-bottom: 22px; }
.hero-eyebrow { display:inline-flex; align-items:center; gap:8px; font-size:13px; font-weight:500;
  letter-spacing:.4px; text-transform:uppercase; color:var(--ink-subtle); margin-bottom:14px; }
.hero-dot { width:9px; height:9px; border-radius:9999px; background:var(--primary);
  box-shadow:0 0 0 4px rgba(94,106,210,.18); }
.hero h1 { font-size:44px; font-weight:600; line-height:1.08; letter-spacing:-1.4px; margin:0 0 10px; }
.hero p  { font-size:18px; line-height:1.5; color:var(--ink-muted); }
/* row of pill "pipeline" chips under the title: Step → Step → Step */
.pipeline-step { font-size:12px; font-weight:500; letter-spacing:.3px; padding:4px 11px;
  border-radius:9999px; background:var(--surface-2); border:1px solid var(--hairline); color:var(--ink-muted); }
.pipeline-arrow { color:var(--ink-tertiary); font-size:12px; }
```
Layout: an eyebrow with the lavender dot ("TECH · STACK · NAMES"), then the large title, a one-line subtitle, and a row of pipeline pills.

### Card (the base container)
```css
.card { background:var(--surface-1); border:1px solid var(--hairline); border-radius:12px;
  padding:20px 22px; margin-bottom:14px; }
.card-accent { border-left:2px solid var(--primary); }   /* highlighted / explanatory card */
.card-title { font-size:15px; font-weight:600; letter-spacing:-.2px; display:flex; align-items:center; gap:9px; margin:0 0 10px; }
.card-body  { font-size:15px; line-height:1.62; color:var(--ink-muted); }
```
**Status stripe pattern:** cards that show an item with a state get `border-left: 2px solid <status color>`, using hairline-strong when idle. This is the main way state is shown.

### Metric tile (KPI strip, 4 across)
```css
.metric { background:var(--surface-1); border:1px solid var(--hairline); border-radius:12px; padding:16px 18px; }
.metric-label { font-size:11px; font-weight:500; letter-spacing:.5px; text-transform:uppercase; color:var(--ink-subtle); margin-bottom:8px; }
.metric-value { font-size:26px; font-weight:600; letter-spacing:-.8px; line-height:1.1; } /* colored by status */
.metric-sub   { font-size:12px; color:var(--ink-tertiary); margin-top:6px; }
```

### Badge / pill
```css
.badge { display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:600;
  letter-spacing:.4px; padding:3px 10px; border-radius:9999px; white-space:nowrap; }
/* color it inline: background:<c>22; color:<c>; border:1px solid <c>44 */
```
Use a glyph plus an uppercase word: `✓ SUPPORTED`, `~ PARTIAL`, `✕ UNSUPPORTED`, `⏸ APPROVAL REQUIRED`.

### Step chip (numbered section header)
```css
.step-chip { font-size:11px; font-weight:600; letter-spacing:.5px; padding:3px 9px; border-radius:9999px;
  background:rgba(94,106,210,.16); color:var(--primary-hover); border:1px solid rgba(94,106,210,.34); }
.panel-title { font-size:17px; font-weight:600; letter-spacing:-.3px; }
.panel-note  { font-size:12.5px; color:var(--ink-tertiary); }
```
Shown as `[STEP 1] Upload sources`, then `[STEP 2] Run`. This guides the user through a linear task.

### Journey stepper (horizontal progress across stages)
```css
.journey { display:flex; gap:6px; overflow-x:auto; }
.jstep { flex:1 1 0; min-width:118px; min-height:64px; display:flex; flex-direction:column; justify-content:space-between;
  background:var(--surface-1); border:1px solid var(--hairline); border-radius:10px; padding:10px 11px; }
.jstep-num { width:18px; height:18px; border-radius:9999px; font-size:10px; font-weight:700;
  display:flex; align-items:center; justify-content:center; }  /* bg <c>22, color <c> */
.jstep-label { font-size:12px; font-weight:500; letter-spacing:-.1px; }
.jstep-state { font-size:9.5px; font-weight:600; letter-spacing:.5px; text-transform:uppercase; }
@keyframes jpulse { 0%,100% { opacity:1 } 50% { opacity:.45 } }
.jstep.active { animation: jpulse 1.5s ease-in-out infinite; }
```
The states are: done (green ✓), active (lavender •, pulsing), pending (tertiary grey, shows the number), skipped (grey –, "not needed") and failed (red ✕). Give non-pending steps a border in `<c>66`.

### Timeline row (live log of steps)
```css
.tl-row { display:flex; align-items:center; gap:12px; padding:11px 16px; margin-bottom:8px; border-radius:10px;
  background:var(--surface-1); border:1px solid var(--hairline); /* + border-left:2px solid <status> */ }
.tl-glyph { width:22px; height:22px; border-radius:9999px; font-size:12px; font-weight:700;
  display:flex; align-items:center; justify-content:center; } /* bg <c>22, color <c> */
.tl-name { font-size:14px; font-weight:500; flex:1; }
.tl-status { font-size:11px; font-weight:600; letter-spacing:.5px; } /* COMPLETED / ROUTED / WAITING FOR YOU / FAILED */
```
Status map: completed = green ✓, warning = amber !, routing = lavender-hover →, waiting = amber …, error = red ✕, running = lavender •.

### Trace / log block (monospace output)
```css
.trace-block { background:var(--surface-1); border:1px solid var(--hairline); border-left:2px solid var(--hairline-strong);
  border-radius:12px; padding:16px 18px; margin-bottom:10px; }
.trace-head { display:flex; align-items:center; gap:10px; margin-bottom:10px; font-size:13px; font-weight:600; letter-spacing:.2px; }
.trace-step { font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--ink-tertiary);
  background:var(--surface-2); border:1px solid var(--hairline); border-radius:4px; padding:1px 6px; } /* [3] */
.trace-body { font-family:'JetBrains Mono',monospace; font-size:12.5px; line-height:1.62; color:var(--ink-subtle); white-space:pre-wrap; margin:0; }
.trace-connector { text-align:center; color:var(--ink-tertiary); font-size:15px; } /* a ↓ between blocks */
```

### Text box with highlighted problems
```css
.summary-box { background:var(--surface-1); border:1px solid var(--hairline); border-radius:12px; padding:20px 22px;
  font-size:15.5px; line-height:1.72; color:var(--ink-muted); }
.hl-bad { background:rgba(224,85,97,.14); border-bottom:1.5px solid var(--danger); color:#ffd7da; padding:1px 3px; border-radius:3px; }
.hl-tag { font-size:10px; font-weight:700; letter-spacing:.5px; color:var(--danger); vertical-align:super; margin-left:3px; }
```
Before/after comparisons go side by side in two columns. The left box has a red left border with a "✕ REJECTED" badge, and the right box has a green left border with a "✓ VERIFIED" badge.

### Item card with evidence (e.g. a verdict or claim)
```css
.claim { background:var(--surface-1); border:1px solid var(--hairline); border-left:2px solid <status>;
  border-radius:12px; padding:16px 18px; margin-bottom:12px; }
.claim-no { font-size:11px; font-weight:500; letter-spacing:.5px; text-transform:uppercase; color:var(--ink-tertiary); }
.claim-text { font-size:15px; line-height:1.55; color:var(--ink); }
.claim-meta { font-size:13px; line-height:1.55; color:var(--ink-subtle); }   /* <b> inside = ink-muted, 500 */
.claim-evidence { margin-top:10px; padding:10px 12px; border-radius:8px; background:var(--surface-2);
  border:1px solid var(--hairline); font-size:12.5px; color:var(--ink-subtle); font-style:italic; }
```
The header row has the item number on the left and the status badge on the right.

### Alert / routing banner (an important event happened)
```css
.routing { border:1.5px dashed var(--primary-hover);
  background:linear-gradient(90deg, rgba(94,106,210,.20), rgba(94,106,210,.06));
  border-radius:12px; padding:18px 22px; }
.routing-glyph { width:30px; height:30px; border-radius:9999px; background:rgba(94,106,210,.26); color:var(--primary-hover);
  display:flex; align-items:center; justify-content:center; font-weight:700; }   /* ↻ */
.routing-title { font-size:16px; font-weight:600; letter-spacing:-.3px; color:var(--primary-hover); }
.routing-edge { font-family:'JetBrains Mono',monospace; font-size:12px; background:var(--canvas);
  border:1px solid rgba(94,106,210,.4); border-radius:6px; padding:3px 9px; color:var(--ink-muted); } /* a → b */
@keyframes routeflash { 0%,100% { border-color:#828fff } 50% { border-color:rgba(94,106,210,.3) } }
.routing.live { animation: routeflash 1.1s ease-in-out infinite; }
```
This is the **only** place a gradient is allowed: a faint accent wash that marks a key moment.

### Final result / verdict card
- Container: `border:1px solid #34343a; border-radius:10px; overflow:hidden; background:linear-gradient(180deg,#0d0f13,#0a0b0e)`.
- **Top:** centered eyebrow ("FINAL VERDICT", 10px, letter-spacing .18em, ink-subtle), then a big stamp (27px/700, status color), e.g. `✅ APPROVED`.
- **Stats row:** a 4-column grid with dividers. Each cell has a value (21px/650, ink) and a label (10px uppercase, letter-spacing .12em, ink-subtle). It becomes 2 columns on mobile.
- **Body:** a label, then the result text with `border-left:2px solid var(--success); padding-left:16px; line-height:1.75`.
- **Correction block** (optional): the rejected item on `#16090b` with a red left border, then the reason in ink-subtle, then a green "→ fixed" line.
- **Footer flow:** on `#08090b`, a row of small uppercase step tags (10.5px, border hairline, radius 5px) joined by `→`. The last step is green.

### Sidebar
- Background surface-1 with `border-right:1px solid var(--hairline)`.
- Section headings are small caps labels: `11px / 600 / letter-spacing .6px / UPPERCASE / ink-subtle`.
- Status pill rows: mono 12px on surface-2, radius 8px, with a 6px dot (green = online, red = problem).
- Helper notes: 12px, ink-tertiary, line-height 1.5.

### Buttons, tabs and inputs
```css
button.primary { background:var(--primary); color:#fff; border:none; border-radius:8px; font-size:14px; font-weight:500;
  padding:10px 14px; transition:background .15s ease; }
button.primary:hover    { background:var(--primary-hover); }
button.primary:focus    { box-shadow:0 0 0 2px rgba(94,105,209,.5); }
button.primary:disabled { background:var(--surface-2); color:var(--ink-tertiary); }
/* secondary: surface-1 bg, ink text, 1px hairline border, same radius/padding */

.tabs { gap:4px; border-bottom:1px solid var(--hairline); }
.tab  { height:40px; padding:0 16px; border-radius:8px 8px 0 0; font-size:14px; font-weight:500; color:var(--ink-subtle); }
.tab[aria-selected=true] { color:var(--ink); background:var(--surface-1); }   /* + 2px lavender underline */

input, textarea { background:var(--surface-1); color:var(--ink); border:1px solid var(--hairline); border-radius:8px; padding:8px 12px; }
input:focus { outline:2px solid rgba(94,105,209,.5); }

.expander { background:var(--surface-1); border:1px solid var(--hairline); border-radius:12px; }
.progress-track { background:var(--surface-2); }  .progress-fill { background:var(--primary); }
```

### Diagram / graph (SVG)
- Background: the canvas color. Nodes are 10–14px rounded rects in surface-1 with a 1.5px stroke.
- Node states: idle = hairline stroke and ink-subtle text · active = surface-2 fill, lavender-hover stroke, pulsing stroke-opacity (1.4s) and a soft 6px glow ring at 28% opacity · done = green stroke · failed = red stroke · waiting = amber stroke, pulsing.
- Labels are 11.5–13px Inter 600 with letter-spacing .4, plus a 9–10px mono subtitle in ink-tertiary.
- Edges are 1.5px in hairline-strong. The active edge is lavender-hover, 2.6px, dashed `6 5` with an animated dash offset.

---

## 6. UX patterns

1. **Guided flow:** use numbered `STEP n` chips. The primary action is one full-width lavender button, disabled (grey) until its inputs are valid. A small mono note beside it shows the input status, e.g. "3 sources · 1,032 words".
2. **Always-visible state:** a stage stepper at the top, a 4-tile metric strip under it, and inside the work area a live diagram on the left and a live timeline on the right.
3. **Live feedback while running:** a progress bar with a text label for the current step. The active item pulses. When something important happens (a retry or reroute), show the dashed accent banner for a moment.
4. **Explain decisions:** every rejection shows *what* was rejected, *why*, and the *evidence*. Put problems inline in the text with a red highlight.
5. **Human-in-the-loop:** an approval panel appears **above the tabs** in a bordered container. It has an amber "⏸ … REQUIRED" badge, the item to review in a box with an amber left border, an optional notes textarea, and two buttons side by side: `✓ Approve` and `✕ Request changes`.
6. **Progressive detail:** the main tab shows the outcome. Other tabs hold the inputs, the per-item checks, memory/data, the full monospace trace and an architecture explainer. Long content goes in collapsible expanders.
7. **Empty states:** a plain card with one sentence on what to do next, e.g. "No run yet. Press Run to …".
8. **Errors:** say what failed and the exact command or step that fixes it.

---

## 7. Do / Don't

**Do**
- Use surface steps and hairlines for structure, and use 2px left-border stripes for status.
- Keep lavender for actions, focus and "active/running" states.
- Use mono for anything technical, like IDs, file names, logs and edges.
- Keep tiny labels uppercase with positive tracking, and headings tight with negative tracking.
- Pair every status color with a glyph (✓ ~ ✕ … ⏸ ↻ →) so state doesn't rely on color alone.

**Don't**
- Don't add a light theme, pure-black backgrounds, drop shadows or decorative gradients (the routing banner and verdict card are the only exceptions).
- Don't add a second accent color, and don't fill large areas with lavender.
- Don't use pill-shaped primary buttons. Buttons are 8px radius; pills are for badges and chips.
- Don't use bright, saturated fills. Colored backgrounds are always the ~13% alpha tint.

---

## 8. Streamlit specifics (if the new project uses Streamlit)

`.streamlit/config.toml`:
```toml
[theme]
base = "dark"
primaryColor = "#5e6ad2"
backgroundColor = "#010102"
secondaryBackgroundColor = "#0f1011"
textColor = "#f7f8f8"
font = "sans serif"

[client]
toolbarMode = "minimal"
```
Then inject the CSS above with `st.markdown("<style>…</style>", unsafe_allow_html=True)` and target these selectors:
`.stApp`, `[data-testid="stSidebar"]`, `.block-container` (padding `1.6rem 2.4rem 4rem`, max-width 1320px), `.stButton > button`, `.stTabs [data-baseweb="tab"]`, `.stTabs [aria-selected="true"]`, `.stTabs [data-baseweb="tab-highlight"]`, `[data-testid="stExpander"]` and `.stProgress`.
Render the custom components as HTML strings through `st.markdown(..., unsafe_allow_html=True)`. Render SVG diagrams through `st.components.v1.html` or `st.iframe`, because markdown strips `<svg>`.

---

## Prompt to give Claude

> Style this app using `UI_THEME_GUIDE.md`. It's a Linear-inspired near-black dark theme: canvas `#010102`, surfaces `#0f1011` / `#141516` / `#18191a`, hairline borders `#23252a`, a single lavender accent `#5e6ad2` (hover `#828fff`), text greys `#f7f8f8` / `#d0d6e0` / `#8a8f98` / `#62666d`, and semantic green `#27a644`, amber `#d9a441` and red `#e05561`, used only as ~13% tints with colored text. Use Inter and JetBrains Mono, 12px card radius, 8px buttons, pill badges, 2px status left-borders, and no shadows. Put all colors in CSS variables first, then build the components and UX patterns from the guide.
