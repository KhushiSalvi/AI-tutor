"""HTML/CSS animation templates for video scenes.

Rendering model: every animated element has data-start="<seconds>" (when, in scene
time, its entrance animation should begin) and a short, real animation-duration (how
long that entrance takes, e.g. 0.6s). A Python-side frame renderer seeks to any time t
by setting `animationDelay = (start - t) + "s"`: a positive delay means "hasn't started
yet" (CSS shows the 0% keyframe, held by animation-fill-mode:both), and a negative delay
means "skip this far into the animation" (shows the keyframe at that progress, or the
100% keyframe once t has passed start+duration). This makes the whole page a
deterministic function of t with no real-time/wall-clock dependency, so we can render
frame-by-frame at any fps and get correct, repeatable results -- confirmed by a motion
test that samples frames at several t and checks they differ before this was shipped.
"""

BASE_CSS = """
  * { box-sizing: border-box; margin: 0; }
  html, body { width: 1280px; height: 720px; background: #181818; overflow: hidden; }
  body { font-family: 'DejaVu Sans', Arial, sans-serif; color: #ececec; }
  .pad { padding: 70px 90px; height: 100%; position: relative; }
  .idx { position: absolute; top: 36px; left: 90px; color: #8a8a8a; font-size: 18px; }
  .cite { position: absolute; bottom: 40px; left: 90px; color: #8a8a8a; font-size: 16px; }
  h1 { font-size: 46px; font-weight: 700; margin-bottom: 36px; }
  .anim { animation-fill-mode: both; animation-play-state: paused; animation-timing-function: ease-out; }
"""


def _shell(body_html, extra_css, index, total, citation):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{BASE_CSS}
{extra_css}
</style></head><body>
<div class="pad">
  <div class="idx">{index}/{total}</div>
  {body_html}
  <div class="cite">{citation}</div>
</div>
</body></html>"""


def title_bullets(scene, index, total):
    title = scene.get("title", "")
    bullets = scene.get("bullets", []) or []
    citation = scene.get("citation", "")
    bullet_html = "\n".join(
        f'<li class="anim b" data-start="{0.6 + i*0.7}" style="animation-name: rise; animation-duration: 0.6s;">{b}</li>'
        for i, b in enumerate(bullets)
    )
    css = """
    h1.anim { animation-name: rise; animation-duration: 0.6s; }
    ul { list-style: none; font-size: 30px; line-height: 1.9; }
    li.b { opacity: 0; position: relative; padding-left: 40px; }
    li.b::before { content: "\\2022"; position: absolute; left: 0; color: #7aa2f7; }
    @keyframes rise {
      0%   { opacity: 0; transform: translateY(24px); }
      100% { opacity: 1; transform: translateY(0); }
    }
    """
    body = f'<h1 class="anim" data-start="0">{title}</h1><ul>{bullet_html}</ul>'
    return _shell(body, css, index, total, citation)


def formula_build(scene, index, total):
    title = scene.get("title", "")
    formula = scene.get("formula", "")
    where = scene.get("formula_where", "")
    citation = scene.get("citation", "")
    tokens = formula.split(" ")
    spans = "\n".join(
        f'<span class="anim tok" data-start="{1.2 + i*0.35}" style="animation-name: pop; animation-duration: 0.35s;">{t}&nbsp;</span>'
        for i, t in enumerate(tokens)
    )
    where_start = 1.2 + len(tokens) * 0.35 + 0.4
    css = """
    h1.anim { animation-name: rise; animation-duration: 0.6s; }
    .box { margin-top: 60px; background: #0d0d0d; border-radius: 14px; padding: 36px 44px;
           font-size: 34px; color: #7aa2f7; min-height: 70px; }
    .tok { display: inline-block; opacity: 0; transform: scale(0.6); }
    .where { font-size: 20px; color: #b4b4b4; opacity: 0; margin-top: 20px; }
    @keyframes rise { 0% { opacity:0; transform: translateY(18px);} 100% { opacity:1; transform: translateY(0);} }
    @keyframes pop   { 0% { opacity:0; transform: scale(0.6);} 100% { opacity:1; transform: scale(1);} }
    """
    body = (f'<h1 class="anim" data-start="0">{title}</h1>'
            f'<div class="box">{spans}</div>'
            f'<div class="where anim" data-start="{where_start}" style="animation-name: rise; animation-duration: 0.6s;">{where}</div>')
    return _shell(body, css, index, total, citation)


def flow(scene, index, total):
    """A horizontal row of labeled nodes with a particle that travels left-to-right
    across them -- generic enough for current flow, data flow, pipeline stages,
    signal chains, instruction flow, etc."""
    title = scene.get("title", "")
    citation = scene.get("citation", "")
    nodes = scene.get("nodes", []) or []
    n = max(len(nodes), 1)
    gap = 1000 / max(n - 1, 1)
    node_starts = [0.3 + i * 0.25 for i in range(n)]
    node_html = "\n".join(
        f'''<div class="node anim" data-start="{node_starts[i]}" style="left:{i*gap}px; animation-name: nodein; animation-duration: 0.45s;">
              <div class="dot"></div><div class="lbl">{lbl}</div>
            </div>'''
        for i, lbl in enumerate(nodes)
    )
    line_w = gap * (n - 1)
    travel_start = node_starts[-1] + 0.6
    travel_dur = max(n - 1, 1) * 1.1
    css = f"""
    h1.anim {{ animation-name: rise; animation-duration: 0.6s; }}
    .stage {{ position: relative; margin-top: 110px; height: 220px; }}
    .line {{ position: absolute; top: 18px; left: 0; width: {line_w}px; height: 4px; background: #3a3a3a; }}
    .node {{ position: absolute; top: 0; width: 140px; text-align: center; opacity: 0; transform: translateY(14px); }}
    .node .dot {{ width: 36px; height: 36px; border-radius: 50%; background: #2f2f2f; border: 3px solid #7aa2f7;
                  margin: 0 auto 14px; }}
    .node .lbl {{ font-size: 20px; }}
    .particle {{ position: absolute; top: 9px; left: 9px; width: 18px; height: 18px; border-radius: 50%;
                 background: #ffb454; box-shadow: 0 0 16px 4px rgba(255,180,84,0.6);
                 animation-name: travel; animation-timing-function: linear; opacity: 0; }}
    @keyframes rise   {{ 0% {{ opacity:0; transform: translateY(18px);}} 100% {{ opacity:1; transform: translateY(0);}} }}
    @keyframes nodein {{ 0% {{ opacity:0; transform: translateY(14px);}} 100% {{ opacity:1; transform: translateY(0);}} }}
    @keyframes travel {{ 0%   {{ opacity: 0; left: 9px; }}
                          1%   {{ opacity: 1; left: 9px; }}
                          100% {{ opacity: 1; left: {line_w - 9}px; }} }}
    """
    body = f'''<h1 class="anim" data-start="0">{title}</h1>
      <div class="stage">
        <div class="line"></div>
        {node_html}
        <div class="particle anim" data-start="{travel_start}" style="animation-duration: {travel_dur}s;"></div>
      </div>'''
    return _shell(body, css, index, total, citation)


def compare(scene, index, total):
    title = scene.get("title", "")
    citation = scene.get("citation", "")
    left = scene.get("left", {}) or {}
    right = scene.get("right", {}) or {}

    def col(side, start, name):
        pts = "".join(f"<li>{p}</li>" for p in side.get("points", []))
        return (f'<div class="col anim" data-start="{start}" style="animation-name: {name}; animation-duration: 0.6s;">'
                f'<div class="head">{side.get("label","")}</div><ul>{pts}</ul></div>')

    css = """
    h1.anim { animation-name: rise; animation-duration: 0.6s; }
    .cols { display: flex; gap: 50px; margin-top: 60px; }
    .col { flex: 1; opacity: 0; background: #202020; border-radius: 14px; padding: 28px 30px; }
    .head { font-size: 26px; font-weight: 700; margin-bottom: 18px; color: #7aa2f7; }
    .col ul { list-style: none; font-size: 22px; line-height: 1.8; }
    .col li { padding-left: 24px; position: relative; }
    .col li::before { content: "\\2022"; position: absolute; left: 0; color: #ffb454; }
    @keyframes rise  { 0% {opacity:0; transform: translateY(18px);} 100% {opacity:1; transform: translateY(0);} }
    @keyframes slideL { 0% {opacity:0; transform: translateX(-30px);} 100% {opacity:1; transform: translateX(0);} }
    @keyframes slideR { 0% {opacity:0; transform: translateX(30px);} 100% {opacity:1; transform: translateX(0);} }
    """
    body = (f'<h1 class="anim" data-start="0">{title}</h1>'
            f'<div class="cols">{col(left, 0.6, "slideL")}{col(right, 1.3, "slideR")}</div>')
    return _shell(body, css, index, total, citation)


def circuit_flow(scene, index, total):
    """Schematic-style component chain with animated current-dot travelling through it.

    Visual JSON schema:
      {"type": "circuit_flow",
       "components": ["R1 10Ω", "C1 10µF", "LED"],   # 2-5 items
       "label_in":  "Vin",   # optional left label
       "label_out": "Vout"}  # optional right label
    """
    title      = scene.get("title", "")
    citation   = scene.get("citation", "")
    components = [str(x) for x in (scene.get("components") or []) if str(x).strip()][:5]
    if not components:
        return title_bullets(scene, index, total)
    label_in   = scene.get("label_in", "Vin")
    label_out  = scene.get("label_out", "Vout")
    n          = len(components)

    # Layout: each box is 170 px wide, gap 60 px; wire on left+right 60 px each
    BOX_W, BOX_H, GAP = 160, 70, 60
    total_w = BOX_W * n + GAP * (n - 1)
    start_x = max(0, (1100 - total_w) // 2)

    boxes_html = ""
    wire_html  = ""
    for i, comp in enumerate(components):
        x = start_x + i * (BOX_W + GAP)
        # wire segment connecting boxes
        if i < n - 1:
            wire_html += (
                f'<div class="wire anim" data-start="{0.3 + i*0.2}" '
                f'style="left:{x+BOX_W}px;animation-name:wirein;animation-duration:0.25s;"></div>'
            )
        boxes_html += (
            f'<div class="cbox anim" data-start="{0.3 + i*0.2}" '
            f'style="left:{x}px;animation-name:boxin;animation-duration:0.4s;">'
            f'{comp}</div>'
        )

    # entry/exit wires
    entry_wire = (
        f'<div class="wire anim" data-start="0.1" '
        f'style="left:{start_x - GAP}px;animation-name:wirein;animation-duration:0.2s;width:{GAP}px;"></div>'
        f'<div class="vlabel anim" data-start="0" '
        f'style="left:{start_x - GAP - 50}px;animation-name:fadein;animation-duration:0.3s;">{label_in}</div>'
    )
    exit_x = start_x + total_w
    exit_wire = (
        f'<div class="wire anim" data-start="{0.3 + (n-1)*0.2}" '
        f'style="left:{exit_x}px;animation-name:wirein;animation-duration:0.2s;width:{GAP}px;"></div>'
        f'<div class="vlabel anim" data-start="{0.5 + (n-1)*0.2}" '
        f'style="left:{exit_x+GAP+4}px;animation-name:fadein;animation-duration:0.3s;">{label_out}</div>'
    )

    particle_start = 0.3 + (n - 1) * 0.2 + 0.5
    particle_travel = total_w + 2 * GAP
    css = f"""
    h1.anim  {{ animation-name: rise; animation-duration: 0.6s; }}
    .stage   {{ position: relative; margin-top: 90px; height: 160px; }}
    .cbox    {{ position: absolute; top: 50px; width: {BOX_W}px; height: {BOX_H}px;
                border: 2.5px solid #7aa2f7; border-radius: 10px;
                display: flex; align-items: center; justify-content: center;
                font-size: 20px; background: #1a1f2e; color: #c0caf5; opacity:0; }}
    .wire    {{ position: absolute; top: 84px; height: 4px; width: {GAP}px;
                background: #7aa2f7; opacity:0; transform-origin:left center; }}
    .vlabel  {{ position: absolute; top: 76px; font-size: 18px; color: #e0af68; opacity:0; }}
    .dot     {{ position: absolute; top: 76px; left: {start_x - GAP}px;
                width: 16px; height: 16px; border-radius: 50%;
                background: #ffb454; box-shadow: 0 0 14px 4px rgba(255,180,84,0.65);
                animation-name: travel; animation-timing-function: linear; opacity:0; }}
    @keyframes rise   {{ 0% {{opacity:0;transform:translateY(18px);}} 100% {{opacity:1;transform:translateY(0);}} }}
    @keyframes boxin  {{ 0% {{opacity:0;transform:scale(0.85);}} 100% {{opacity:1;transform:scale(1);}} }}
    @keyframes wirein {{ 0% {{opacity:0;transform:scaleX(0);}} 100% {{opacity:1;transform:scaleX(1);}} }}
    @keyframes fadein {{ 0% {{opacity:0;}} 100% {{opacity:1;}} }}
    @keyframes travel {{ 0%  {{opacity:0; left:{start_x - GAP}px;}}
                          2%  {{opacity:1; left:{start_x - GAP}px;}}
                          100%{{opacity:1; left:{start_x - GAP + particle_travel}px;}} }}
    """
    body = (
        f'<h1 class="anim" data-start="0">{title}</h1>'
        f'<div class="stage">'
        f'{entry_wire}{wire_html}{exit_wire}{boxes_html}'
        f'<div class="dot anim" data-start="{particle_start}" '
        f'style="animation-duration:{max(n*0.9,1.5):.1f}s;"></div>'
        f'</div>'
    )
    return _shell(body, css, index, total, citation)


def waveform_plot(scene, index, total):
    """Animated SVG waveform drawn on a grid.

    Visual JSON schema (all numeric, so LLM picks a shape_id; Python computes points):
      {"type": "waveform_plot",
       "shape": "sine"|"rc_charge"|"square"|"sawtooth",
       "x_label": "Time (s)",
       "y_label": "Voltage (V)",
       "highlight_x": 0.5}   # 0–1 fraction where a dashed vertical marker appears
    """
    import math

    title     = scene.get("title", "")
    citation  = scene.get("citation", "")
    shape     = scene.get("shape", "sine")
    x_label   = scene.get("x_label", "Time")
    y_label   = scene.get("y_label", "Amplitude")
    highlight = float(scene.get("highlight_x", -1))  # -1 means no marker

    # SVG canvas
    W, H = 900, 380
    PL, PR, PT, PB = 70, 30, 20, 60   # padding left/right/top/bottom
    plot_w = W - PL - PR
    plot_h = H - PT - PB

    # Compute curve points with numpy-like math (plain Python, no numpy needed)
    N = 120
    xs = [i / (N - 1) for i in range(N)]

    if shape == "rc_charge":
        ys = [1 - math.exp(-5 * x) for x in xs]           # V(t) = 1 - e^(-t/RC), tau=0.2
    elif shape == "square":
        ys = [1.0 if (x * 4) % 1 < 0.5 else 0.0 for x in xs]
    elif shape == "sawtooth":
        ys = [(x * 4) % 1 for x in xs]
    else:  # default: sine
        ys = [(math.sin(x * 2 * math.pi * 2) + 1) / 2 for x in xs]  # 2 cycles, normalised 0-1

    # Map to SVG coordinates (y flipped)
    def px(x, y):
        sx = PL + x * plot_w
        sy = PT + (1 - y) * plot_h
        return sx, sy

    # Build polyline points string
    pts_str = " ".join(f"{px(x,y)[0]:.1f},{px(x,y)[1]:.1f}" for x, y in zip(xs, ys))

    # Highlight marker
    marker_svg = ""
    if 0 <= highlight <= 1:
        mx, _ = px(highlight, 0)
        marker_svg = (
            f'<line x1="{mx:.1f}" y1="{PT}" x2="{mx:.1f}" y2="{PT+plot_h}" '
            f'stroke="#f7768e" stroke-width="2" stroke-dasharray="6,4" opacity="0"/>'
            f'<animate attributeName="opacity" begin="1.4s" dur="0.4s" '
            f'fill="freeze" from="0" to="1"/>'
        )
        # Wrap marker in a group so the animate works
        marker_svg = (
            f'<g id="marker"><line x1="{mx:.1f}" y1="{PT}" x2="{mx:.1f}" y2="{PT+plot_h}" '
            f'stroke="#f7768e" stroke-width="2" stroke-dasharray="6,4"/>'
            f'<animate attributeName="opacity" xlink:href="#marker" begin="1.4s" dur="0.4s" '
            f'fill="freeze" from="0" to="1"/></g>'
        )

    path_len_approx = N * 8   # crude upper bound for stroke-dasharray animation

    svg = f"""
    <svg width="{W}" height="{H}" style="display:block;margin:auto;">
      <!-- Grid -->
      <line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+plot_h}" stroke="#3a3a3a" stroke-width="2"/>
      <line x1="{PL}" y1="{PT+plot_h}" x2="{PL+plot_w}" y2="{PT+plot_h}" stroke="#3a3a3a" stroke-width="2"/>
      {"".join(
          f'<line x1="{PL}" y1="{PT + i*plot_h//4}" x2="{PL+plot_w}" y2="{PT + i*plot_h//4}" stroke="#2a2a2a" stroke-width="1"/>'
          for i in range(1, 4)
      )}
      <!-- Animated curve: draws itself via stroke-dashoffset -->
      <polyline id="curve" points="{pts_str}"
        fill="none" stroke="#7aa2f7" stroke-width="3" stroke-linecap="round"
        stroke-dasharray="{path_len_approx}" stroke-dashoffset="{path_len_approx}">
        <animate attributeName="stroke-dashoffset" from="{path_len_approx}" to="0"
          begin="0.6s" dur="1.2s" fill="freeze" calcMode="linear"/>
      </polyline>
      <!-- Axes labels -->
      <text x="{PL + plot_w//2}" y="{PT+plot_h+50}" fill="#8a8a8a" font-size="18" text-anchor="middle">{x_label}</text>
      <text x="16" y="{PT + plot_h//2}" fill="#8a8a8a" font-size="18" text-anchor="middle"
        transform="rotate(-90,16,{PT + plot_h//2})">{y_label}</text>
      {marker_svg}
    </svg>
    """

    css = """
    h1.anim { animation-name: rise; animation-duration: 0.6s; }
    @keyframes rise { 0% {opacity:0;transform:translateY(18px);} 100% {opacity:1;transform:translateY(0);} }
    """
    body = f'<h1 class="anim" data-start="0">{title}</h1>{svg}'
    return _shell(body, css, index, total, citation)


def pipeline_timing(scene, index, total):
    """CPU-pipeline style timing grid.

    Visual JSON schema:
      {"type": "pipeline_timing",
       "stages": ["IF", "ID", "EX", "MEM", "WB"],
       "cycles": 7,       # number of clock cycles to show (max 9)
       "instructions": 3} # how many instruction rows (max 4)
    """
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    stages   = [str(s) for s in (scene.get("stages") or ["IF","ID","EX","MEM","WB"])][:6]
    n_cycles = min(int(scene.get("cycles") or 8), 9)
    n_instr  = min(int(scene.get("instructions") or 3), 4)
    n_stages = len(stages)

    CELL_W, CELL_H = 100, 52
    HEAD_H = 46  # header row height
    LEFT_W = 70  # instruction label column

    grid_w = LEFT_W + n_cycles * CELL_W
    grid_h = HEAD_H + n_instr * CELL_H

    STAGE_COLORS = ["#3d59a1","#1a6a4a","#6b2d2d","#5a3e7a","#7a5a1a","#1a5a6a"]

    rows_html = ""
    cells_html = ""

    # Header row (cycle numbers)
    hdr = "".join(
        f'<div class="hdr-cell" style="left:{LEFT_W + c*CELL_W}px;">{c+1}</div>'
        for c in range(n_cycles)
    )

    # Instruction rows
    total_cells = 0
    for instr in range(n_instr):
        rows_html += (
            f'<div class="instr-label" style="top:{HEAD_H + instr*CELL_H}px;">I{instr+1}</div>'
        )
        for s_idx, stage in enumerate(stages):
            cycle = instr + s_idx          # diagonal pipeline
            if cycle >= n_cycles:
                break
            col_idx = s_idx % len(STAGE_COLORS)
            color = STAGE_COLORS[col_idx]
            delay = 0.4 + total_cells * 0.08
            cells_html += (
                f'<div class="pcell anim" data-start="{delay:.2f}" '
                f'style="left:{LEFT_W + cycle*CELL_W}px;top:{HEAD_H + instr*CELL_H}px;'
                f'background:{color};animation-name:popin;animation-duration:0.3s;">'
                f'{stage}</div>'
            )
            total_cells += 1

    css = f"""
    h1.anim    {{ animation-name: rise; animation-duration: 0.6s; }}
    .grid-wrap {{ position: relative; margin-top: 50px; width: {grid_w}px; height: {grid_h}px;
                  border: 1px solid #3a3a3a; overflow: hidden; margin-left: auto; margin-right: auto; }}
    .hdr-cell  {{ position: absolute; top: 0; width: {CELL_W}px; height: {HEAD_H}px;
                  border-left: 1px solid #3a3a3a; border-bottom: 2px solid #4a4a5a;
                  display: flex; align-items: center; justify-content: center;
                  font-size: 15px; color: #8a8a8a; }}
    .instr-label {{ position: absolute; left: 0; width: {LEFT_W}px; height: {CELL_H}px;
                    border-bottom: 1px solid #2a2a2a; display: flex; align-items: center;
                    justify-content: center; font-size: 15px; color: #a9b1d6; }}
    .pcell     {{ position: absolute; width: {CELL_W - 4}px; height: {CELL_H - 4}px;
                  margin: 2px; border-radius: 6px; display: flex; align-items: center;
                  justify-content: center; font-size: 15px; color: #fff; font-weight: 600;
                  opacity: 0; }}
    @keyframes rise  {{ 0% {{opacity:0;transform:translateY(18px);}} 100% {{opacity:1;transform:translateY(0);}} }}
    @keyframes popin {{ 0% {{opacity:0;transform:scale(0.6);}} 100% {{opacity:1;transform:scale(1);}} }}
    """
    body = (
        f'<h1 class="anim" data-start="0">{title}</h1>'
        f'<div class="grid-wrap">'
        f'<div class="instr-label" style="top:0;height:{HEAD_H}px;border-bottom:2px solid #4a4a5a;">#</div>'
        f'{hdr}{rows_html}{cells_html}</div>'
    )
    return _shell(body, css, index, total, citation)


def logic_truth(scene, index, total):
    """Logic gate symbol + animated truth-table rows revealed one at a time.

    Visual JSON schema:
      {"type": "logic_truth",
       "gate": "AND"|"OR"|"NOT"|"NAND"|"NOR"|"XOR",
       "inputs": ["A","B"],        # 1-2 input names
       "output": "Y"}
    The truth table is computed entirely in Python — LLM never invents values.
    """
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    gate     = str(scene.get("gate", "AND")).upper()
    inputs   = [str(x) for x in (scene.get("inputs") or ["A", "B"])][:2]
    output   = str(scene.get("output", "Y"))

    # --- Compute truth table in Python (never LLM-generated) ---
    n_inputs = len(inputs)
    rows = []
    for i in range(2 ** n_inputs):
        vals = [(i >> (n_inputs - 1 - j)) & 1 for j in range(n_inputs)]
        a, b = vals[0], (vals[1] if n_inputs > 1 else 0)
        if gate == "AND":   out = a & b
        elif gate == "OR":  out = a | b
        elif gate == "NOT": out = 1 - a
        elif gate == "NAND":out = 1 - (a & b)
        elif gate == "NOR": out = 1 - (a | b)
        elif gate == "XOR": out = a ^ b
        else:               out = a & b
        rows.append(vals + [out])

    # --- Gate SVG (simple symbolic) ---
    GATE_SVG = {
        "AND":  '<path d="M20,10 L60,10 Q90,10 90,35 Q90,60 60,60 L20,60 Z" fill="none" stroke="#7aa2f7" stroke-width="3"/><line x1="90" y1="35" x2="110" y2="35" stroke="#7aa2f7" stroke-width="3"/>',
        "OR":   '<path d="M20,10 Q50,10 80,35 Q50,60 20,60 Q40,45 40,35 Q40,25 20,10Z" fill="none" stroke="#7aa2f7" stroke-width="3"/><line x1="80" y1="35" x2="110" y2="35" stroke="#7aa2f7" stroke-width="3"/>',
        "NOT":  '<polygon points="20,10 80,35 20,60" fill="none" stroke="#7aa2f7" stroke-width="3"/><circle cx="88" cy="35" r="8" fill="none" stroke="#7aa2f7" stroke-width="3"/><line x1="96" y1="35" x2="110" y2="35" stroke="#7aa2f7" stroke-width="3"/>',
        "NAND": '<path d="M20,10 L60,10 Q90,10 90,35 Q90,60 60,60 L20,60 Z" fill="none" stroke="#7aa2f7" stroke-width="3"/><circle cx="98" cy="35" r="8" fill="none" stroke="#7aa2f7" stroke-width="3"/><line x1="106" y1="35" x2="120" y2="35" stroke="#7aa2f7" stroke-width="3"/>',
        "NOR":  '<path d="M20,10 Q50,10 80,35 Q50,60 20,60 Q40,45 40,35 Q40,25 20,10Z" fill="none" stroke="#7aa2f7" stroke-width="3"/><circle cx="88" cy="35" r="8" fill="none" stroke="#7aa2f7" stroke-width="3"/><line x1="96" y1="35" x2="110" y2="35" stroke="#7aa2f7" stroke-width="3"/>',
        "XOR":  '<path d="M25,10 Q55,10 85,35 Q55,60 25,60 Q45,45 45,35 Q45,25 25,10Z" fill="none" stroke="#7aa2f7" stroke-width="3"/><path d="M15,10 Q32,35 15,60" fill="none" stroke="#7aa2f7" stroke-width="3"/><line x1="85" y1="35" x2="110" y2="35" stroke="#7aa2f7" stroke-width="3"/>',
    }
    gate_svg_inner = GATE_SVG.get(gate, GATE_SVG["AND"])
    # Input wire(s)
    if n_inputs == 2:
        in_wires = ('<line x1="0" y1="20" x2="20" y2="20" stroke="#7aa2f7" stroke-width="2"/>'
                    '<line x1="0" y1="50" x2="20" y2="50" stroke="#7aa2f7" stroke-width="2"/>')
        in_labels = (f'<text x="-8" y="23" fill="#e0af68" font-size="14" text-anchor="end">{inputs[0]}</text>'
                     f'<text x="-8" y="53" fill="#e0af68" font-size="14" text-anchor="end">{inputs[1]}</text>')
    else:
        in_wires  = '<line x1="0" y1="35" x2="20" y2="35" stroke="#7aa2f7" stroke-width="2"/>'
        in_labels = f'<text x="-8" y="38" fill="#e0af68" font-size="14" text-anchor="end">{inputs[0]}</text>'

    out_label = f'<text x="118" y="38" fill="#e0af68" font-size="14">{output}</text>'
    gate_full_svg = (
        f'<svg width="140" height="70" style="overflow:visible;">'
        f'{gate_svg_inner}{in_wires}{in_labels}{out_label}</svg>'
    )

    # --- Truth table ---
    col_names = inputs + [output]
    thead = "".join(f"<th>{c}</th>" for c in col_names)
    tbody = ""
    for r_idx, row in enumerate(rows):
        delay = 0.8 + r_idx * 0.4
        out_val = row[-1]
        out_color = "#9ece6a" if out_val else "#f7768e"
        cells = "".join(f"<td>{v}</td>" for v in row[:-1])
        cells += f'<td style="color:{out_color};font-weight:700;">{out_val}</td>'
        tbody += (
            f'<tr class="anim trow" data-start="{delay:.1f}" '
            f'style="animation-name:rowin;animation-duration:0.35s;">{cells}</tr>'
        )

    css = """
    h1.anim  { animation-name: rise; animation-duration: 0.6s; }
    .layout  { display: flex; gap: 80px; align-items: flex-start; margin-top: 40px; }
    .gate-box { flex: 0 0 auto; }
    table    { border-collapse: collapse; font-size: 22px; }
    th       { padding: 10px 22px; border-bottom: 2px solid #4a4a5a;
               color: #7aa2f7; font-weight: 700; text-align: center; }
    td       { padding: 8px 22px; border-bottom: 1px solid #2a2a2a; text-align: center; color: #c0caf5; }
    .trow    { opacity: 0; }
    @keyframes rise  { 0% {opacity:0;transform:translateY(18px);} 100% {opacity:1;transform:translateY(0);} }
    @keyframes rowin { 0% {opacity:0;transform:translateX(-16px);} 100% {opacity:1;transform:translateX(0);} }
    """
    body = (
        f'<h1 class="anim" data-start="0">{title}</h1>'
        f'<div class="layout">'
        f'<div class="gate-box">{gate_full_svg}'
        f'<div style="text-align:center;font-size:18px;color:#565f89;margin-top:10px;">{gate} Gate</div>'
        f'</div>'
        f'<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>'
        f'</div>'
    )
    return _shell(body, css, index, total, citation)


def block_diagram(scene, index, total):
    """Labeled boxes connected by arrows, with animated highlight pulses.

    Visual JSON schema:
      {"type": "block_diagram",
       "blocks": [
         {"id": "cpu",  "label": "CPU"},
         {"id": "mem",  "label": "Memory"},
         {"id": "io",   "label": "I/O"}
       ],
       "edges": [
         {"from": "cpu", "to": "mem", "label": "data bus"},
         {"from": "cpu", "to": "io",  "label": "control"}
       ],
       "highlight": "cpu"}   # optional: which block pulses after all appear
    """
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    blocks   = [b for b in (scene.get("blocks") or []) if b.get("id") and b.get("label")][:6]
    edges    = scene.get("edges") or []
    highlight_id = scene.get("highlight", "")

    if not blocks:
        return title_bullets(scene, index, total)

    n = len(blocks)

    # Simple horizontal layout (auto-wrap at 3 per row)
    COLS   = min(n, 3)
    ROWS   = (n + COLS - 1) // COLS
    BW, BH = 220, 70
    H_GAP, V_GAP = 100, 90
    TOTAL_W = COLS * BW + (COLS - 1) * H_GAP
    START_X = max(0, (1100 - TOTAL_W) // 2)
    START_Y = 10

    pos = {}  # id -> (cx, cy) center positions
    blocks_html = ""
    for idx, blk in enumerate(blocks):
        col = idx % COLS
        row = idx // COLS
        x = START_X + col * (BW + H_GAP)
        y = START_Y + row * (BH + V_GAP)
        cx = x + BW // 2
        cy = y + BH // 2
        pos[blk["id"]] = (cx, cy)

        delay = 0.3 + idx * 0.2
        is_highlight = blk["id"] == highlight_id
        pulse_anim = " pulse" if is_highlight else ""
        pulse_delay = delay + 0.5 * n + 0.4
        blocks_html += (
            f'<div class="blk anim{pulse_anim}" data-start="{delay:.2f}" '
            f'style="left:{x}px;top:{y}px;animation-name:blockin;animation-duration:0.4s;'
            + (f'animation-name:blockin,glow;animation-duration:0.4s,1.2s;animation-delay:{delay:.2f}s,{pulse_delay:.2f}s;animation-iteration-count:1,3;' if is_highlight else "")
            + f'">{blk["label"]}</div>'
        )

    # Edges as SVG arrows overlaid on top
    arrow_svgs = ""
    for e_idx, edge in enumerate(edges):
        src, dst = edge.get("from", ""), edge.get("to", "")
        if src not in pos or dst not in pos:
            continue
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        label = edge.get("label", "")
        delay = 0.3 + n * 0.2 + e_idx * 0.25
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        arrow_svgs += (
            f'<g class="arrow anim" data-start="{delay:.2f}" '
            f'style="animation-name:fadein;animation-duration:0.4s;">'
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#565f89" stroke-width="2.5" marker-end="url(#arr)"/>'
            + (f'<text x="{mx}" y="{my-8}" fill="#8a8a8a" font-size="15" text-anchor="middle">{label}</text>' if label else "")
            + f'</g>'
        )

    total_height = START_Y + ROWS * (BH + V_GAP) + 20
    overlay_svg = (
        f'<svg style="position:absolute;top:140px;left:0;width:1100px;height:{total_height}px;pointer-events:none;">'
        f'<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
        f'<path d="M0,0 L0,6 L8,3 Z" fill="#565f89"/></marker></defs>'
        f'{arrow_svgs}</svg>'
    )

    css = f"""
    h1.anim  {{ animation-name: rise; animation-duration: 0.6s; }}
    .stage   {{ position: relative; margin-top: 50px; height: {total_height + 30}px; }}
    .blk     {{ position: absolute; width: {BW}px; height: {BH}px;
                border: 2px solid #565f89; border-radius: 10px;
                display: flex; align-items: center; justify-content: center;
                font-size: 20px; background: #1a1f2e; color: #c0caf5; opacity: 0; }}
    .arrow   {{ opacity: 0; }}
    @keyframes rise    {{ 0% {{opacity:0;transform:translateY(18px);}} 100% {{opacity:1;transform:translateY(0);}} }}
    @keyframes blockin {{ 0% {{opacity:0;transform:scale(0.8);}} 100% {{opacity:1;transform:scale(1);}} }}
    @keyframes fadein  {{ 0% {{opacity:0;}} 100% {{opacity:1;}} }}
    @keyframes glow    {{ 0%,100% {{box-shadow:none;border-color:#565f89;}}
                          50%     {{box-shadow:0 0 18px 4px rgba(122,162,247,0.5);border-color:#7aa2f7;}} }}
    """
    body = (
        f'<h1 class="anim" data-start="0">{title}</h1>'
        f'<div class="stage">{blocks_html}{overlay_svg}</div>'
    )
    return _shell(body, css, index, total, citation)


def phasor_diagram(scene, index, total):
    """Polar phasor plot with animated arrow draw-in. Used for AC circuits, power factor, impedance."""
    import math, html as _html
    title    = scene.get("title", "Phasor Diagram")
    citation = scene.get("citation", "")
    phasors  = (scene.get("phasors") or [])[:4]
    if not phasors:
        phasors = [{"label": "V", "magnitude": 1.0, "angle_deg": 0, "color": "#7aa2f7"}]

    CX, CY, R_SCALE = 250, 250, 170  # SVG center and scale

    # Axes
    axes = (
        f'<line x1="80" y1="{CY}" x2="420" y2="{CY}" stroke="#444" stroke-width="1.5" stroke-dasharray="6,4"/>'
        f'<line x1="{CX}" y1="80" x2="{CX}" y2="420" stroke="#444" stroke-width="1.5" stroke-dasharray="6,4"/>'
        f'<text x="425" y="{CY+5}" fill="#666" font-size="14">Re</text>'
        f'<text x="{CX+5}" y="75" fill="#666" font-size="14">Im</text>'
    )
    # Concentric circles
    circles = "".join(
        f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="none" stroke="#2a2a2a" stroke-width="1"/>'
        for r in [57, 113, 170]
    )

    arrows_html = ""
    legend_html = ""
    for pi, ph in enumerate(phasors):
        mag   = max(0.05, min(1.0, float(ph.get("magnitude", 1.0))))
        ang   = float(ph.get("angle_deg", 0))
        color = str(ph.get("color", "#7aa2f7"))
        label = _html.escape(str(ph.get("label", f"P{pi+1}")))
        rad   = math.radians(-ang)   # SVG Y is inverted
        length = mag * R_SCALE
        ex    = CX + length * math.cos(rad)
        ey    = CY + length * math.sin(rad)
        # Arrowhead
        head_len = 12
        ax1 = ex - head_len * math.cos(rad - 0.4)
        ay1 = ey - head_len * math.sin(rad - 0.4)
        ax2 = ex - head_len * math.cos(rad + 0.4)
        ay2 = ey - head_len * math.sin(rad + 0.4)
        full_len = max(1, length + head_len)
        t_start = 0.4 + pi * 0.5

        arrows_html += (
            f'<g class="anim" data-start="{t_start}" style="animation-name:fadein;animation-duration:0.8s;">'
            f'<line x1="{CX}" y1="{CY}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="{color}" stroke-width="3" stroke-linecap="round"'
            f' stroke-dasharray="{full_len:.0f}" stroke-dashoffset="{full_len:.0f}">'
            f'<animate attributeName="stroke-dashoffset" from="{full_len:.0f}" to="0" '
            f'dur="0.7s" begin="indefinite" fill="freeze" id="ph{pi}"/>'
            f'</animate></line>'
            f'<polygon points="{ex:.1f},{ey:.1f} {ax1:.1f},{ay1:.1f} {ax2:.1f},{ay2:.1f}" fill="{color}"/>'
            f'<text x="{ex + 10 * math.cos(rad):.1f}" y="{ey + 10 * math.sin(rad) + 5:.1f}" '
            f'fill="{color}" font-size="18" font-weight="700">{label}</text>'
            f'</g>'
        )
        legend_html += (
            f'<div class="anim leg" data-start="{t_start + 0.3}" '
            f'style="animation-name:rise;animation-duration:0.5s;">'
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
            f'background:{color};margin-right:8px;vertical-align:middle;"></span>'
            f'<span style="color:{color};font-weight:600;">{label}</span>'
            f'<span style="color:#8a8a8a;font-size:16px;"> &#8212; mag {mag:.2f}, {ang:.0f}&#176;</span>'
            f'</div>'
        )

    svg = (
        f'<svg width="500" height="500" style="position:absolute;right:60px;top:80px;">'
        f'{circles}{axes}{arrows_html}</svg>'
    )
    css = """
    h1.anim  { animation-name: rise; animation-duration: 0.6s; font-size: 38px; max-width: 580px; }
    .leg     { opacity: 0; margin-bottom: 12px; font-size: 18px; }
    @keyframes rise   { 0%{opacity:0;transform:translateY(16px);} 100%{opacity:1;transform:translateY(0);} }
    @keyframes fadein { 0%{opacity:0;} 100%{opacity:1;} }
    """
    body = (
        f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>'
        f'<div style="margin-top:20px;">{legend_html}</div>'
        f'{svg}'
    )
    return _shell(body, css, index, total, citation)


def bode_plot(scene, index, total):
    """Log-frequency Bode magnitude plot with animated line draw. Source data computed from poles/zeros."""
    import math, html as _html
    title        = scene.get("title", "Bode Plot")
    citation     = scene.get("citation", "")
    poles        = [float(p) for p in (scene.get("poles") or [1000])][:4]
    zeros        = [float(z) for z in (scene.get("zeros") or [])][:4]
    dc_gain_db   = float(scene.get("dc_gain_db", 0))
    x_label      = str(scene.get("x_label", "Frequency (Hz)"))[:30]
    highlight_f  = scene.get("highlight_freq")

    # SVG plot area
    PW, PH = 900, 380
    ML, MR, MT, MB = 80, 30, 20, 60   # margins

    f_min, f_max = 1.0, max(poles + zeros + [1]) * 100
    f_min = max(0.1, f_min)
    n_pts = 120
    freqs = [f_min * (f_max / f_min) ** (i / (n_pts - 1)) for i in range(n_pts)]

    def gain_db(f):
        g = dc_gain_db
        for z in zeros:
            g += 10 * math.log10(1 + (f / z) ** 2)
        for p in poles:
            g -= 10 * math.log10(1 + (f / p) ** 2)
        return g

    dbs = [gain_db(f) for f in freqs]
    db_min, db_max = min(dbs) - 10, max(dbs) + 10

    def px(f):
        return ML + (math.log10(f / f_min) / math.log10(f_max / f_min)) * (PW - ML - MR)

    def py(db):
        return MT + (1 - (db - db_min) / (db_max - db_min)) * (PH - MT - MB)

    # Grid lines (decades)
    grid = ""
    decade = 10 ** math.ceil(math.log10(f_min))
    while decade <= f_max:
        x = px(decade)
        grid += f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{PH-MB}" stroke="#2a2a2a" stroke-width="1"/>'
        grid += f'<text x="{x:.1f}" y="{PH-MB+16}" fill="#555" font-size="11" text-anchor="middle">{decade:.0f}</text>'
        decade *= 10

    # dB grid
    db_step = 20 if (db_max - db_min) > 60 else 10
    db_tick = int(db_min // db_step) * db_step
    while db_tick <= db_max:
        y = py(db_tick)
        grid += f'<line x1="{ML}" y1="{y:.1f}" x2="{PW-MR}" y2="{y:.1f}" stroke="#2a2a2a" stroke-width="1"/>'
        grid += f'<text x="{ML-6}" y="{y+4:.1f}" fill="#555" font-size="11" text-anchor="end">{db_tick}</text>'
        db_tick += db_step

    # Axes
    axes = (
        f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{PH-MB}" stroke="#555" stroke-width="2"/>'
        f'<line x1="{ML}" y1="{PH-MB}" x2="{PW-MR}" y2="{PH-MB}" stroke="#555" stroke-width="2"/>'
        f'<text x="{PW//2}" y="{PH-MB+34}" fill="#888" font-size="13" text-anchor="middle">{_html.escape(x_label)}</text>'
        f'<text x="14" y="{PH//2}" fill="#888" font-size="13" text-anchor="middle" transform="rotate(-90,14,{PH//2})">|H(j&#969;)| dB</text>'
    )

    # Main Bode curve as animated polyline
    pts = " ".join(f"{px(f):.1f},{py(db):.1f}" for f, db in zip(freqs, dbs))
    total_len = sum(
        math.hypot(px(freqs[i+1]) - px(freqs[i]), py(dbs[i+1]) - py(dbs[i]))
        for i in range(len(freqs)-1)
    )
    curve = (
        f'<polyline class="anim" data-start="0.5" points="{pts}" '
        f'fill="none" stroke="#7aa2f7" stroke-width="3" stroke-linecap="round" '
        f'stroke-dasharray="{total_len:.0f}" '
        f'style="stroke-dashoffset:{total_len:.0f};animation-name:drawline;animation-duration:2.5s;"/>'
    )

    # Corner frequency markers
    markers = ""
    for fi, fp in enumerate(poles + zeros):
        if f_min <= fp <= f_max:
            x = px(fp)
            color = "#f7768e" if fi < len(poles) else "#9ece6a"
            label = f"fp={fp:.0f}" if fi < len(poles) else f"fz={fp:.0f}"
            markers += (
                f'<line class="anim" data-start="{2.8 + fi*0.3}" x1="{x:.1f}" y1="{MT}" '
                f'x2="{x:.1f}" y2="{PH-MB}" stroke="{color}" stroke-width="1.5" '
                f'stroke-dasharray="6,4" style="animation-name:fadein;animation-duration:0.4s;"/>'
                f'<text class="anim" data-start="{2.8 + fi*0.3}" x="{x:.1f}" y="{MT-4}" '
                f'fill="{color}" font-size="12" text-anchor="middle" '
                f'style="animation-name:fadein;animation-duration:0.4s;">{label}</text>'
            )

    svg = (
        f'<svg width="{PW}" height="{PH}" style="position:absolute;left:60px;top:140px;">'
        f'{grid}{axes}{curve}{markers}</svg>'
    )
    css = f"""
    h1.anim {{ animation-name: rise; animation-duration: 0.6s; font-size: 36px; }}
    @keyframes rise     {{ 0%{{opacity:0;transform:translateY(16px);}} 100%{{opacity:1;transform:translateY(0);}} }}
    @keyframes fadein   {{ 0%{{opacity:0;}} 100%{{opacity:1;}} }}
    @keyframes drawline {{ 0%{{stroke-dashoffset:{total_len:.0f};}} 100%{{stroke-dashoffset:0;}} }}
    """
    body = (
        f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>'
        f'{svg}'
    )
    return _shell(body, css, index, total, citation)


def transistor_iv(scene, index, total):
    """MOSFET/BJT ID-VDS family of curves. Data computed from device equations, not invented."""
    import math, html as _html
    title    = scene.get("title", "Transistor I-V Characteristics")
    citation = scene.get("citation", "")
    device   = str(scene.get("device", "MOSFET")).upper()
    vgs_vals = [float(v) for v in (scene.get("vgs_values") or [1.5, 2.0, 2.5, 3.0])][:5]
    vth      = float(scene.get("vth", 1.0))
    highlight = str(scene.get("highlight_region", "")).lower()

    PW, PH = 850, 440
    ML, MR, MT, MB = 80, 30, 30, 60

    k = 2.0  # process constant (normalized)
    vds_max = max(vgs_vals) * 1.5
    id_max = k / 2 * (max(vgs_vals) - vth) ** 2 * 1.1 if max(vgs_vals) > vth else 1.0

    def px(v): return ML + (v / vds_max) * (PW - ML - MR)
    def py(i): return PH - MB - (i / id_max) * (PH - MT - MB)

    # Axes
    axes = (
        f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{PH-MB}" stroke="#666" stroke-width="2"/>'
        f'<line x1="{ML}" y1="{PH-MB}" x2="{PW-MR}" y2="{PH-MB}" stroke="#666" stroke-width="2"/>'
        f'<text x="{PW//2}" y="{PH}" fill="#888" font-size="13" text-anchor="middle">V_DS (V)</text>'
        f'<text x="14" y="{PH//2}" fill="#888" font-size="13" text-anchor="middle" transform="rotate(-90,14,{PH//2})">I_D (mA)</text>'
    )
    # VDS tick marks
    ticks = ""
    for tv in [1, 2, 3, 4, 5]:
        if tv <= vds_max:
            x = px(tv)
            ticks += f'<line x1="{x:.1f}" y1="{PH-MB}" x2="{x:.1f}" y2="{PH-MB+5}" stroke="#666"/>'
            ticks += f'<text x="{x:.1f}" y="{PH-MB+18}" fill="#888" font-size="11" text-anchor="middle">{tv}</text>'

    COLORS = ["#7aa2f7", "#9ece6a", "#e0af68", "#f7768e", "#bb9af7"]

    curves_html = ""
    sat_pts = []  # for saturation boundary
    for ci, vgs in enumerate(vgs_vals):
        if vgs <= vth:
            continue
        overdrive = vgs - vth
        vds_sat = overdrive
        id_sat = k / 2 * overdrive ** 2
        # Build polyline points
        n_pts = 80
        pts_lin, pts_sat = [], []
        for j in range(n_pts + 1):
            vds = vds_max * j / n_pts
            if vds <= vds_sat:
                id_v = k * (overdrive * vds - vds ** 2 / 2)
                pts_lin.append(f"{px(vds):.1f},{py(id_v):.1f}")
            else:
                pts_sat.append(f"{px(vds):.1f},{py(id_sat):.1f}")
        pts_all = pts_lin + pts_sat
        color = COLORS[ci % len(COLORS)]
        t_start = 0.8 + ci * 0.5
        label_vds = vds_max * 0.98
        label_id = id_sat

        curves_html += (
            f'<g class="anim" data-start="{t_start}" style="animation-name:fadein;animation-duration:0.6s;">'
            f'<polyline points="{" ".join(pts_all)}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
            f'<text x="{px(label_vds):.1f}" y="{py(label_id)-8:.1f}" fill="{color}" font-size="13" text-anchor="end">'
            f'V_GS={vgs:.1f}V</text>'
            f'</g>'
        )
        sat_pts.append(f"{px(vds_sat):.1f},{py(id_sat):.1f}")

    # Saturation boundary parabola
    sat_boundary = ""
    if len(sat_pts) >= 2:
        sat_boundary = (
            f'<polyline class="anim" data-start="{0.5 + len(vgs_vals)*0.5}" '
            f'points="{ML},{PH-MB} {" ".join(sat_pts)}" '
            f'fill="none" stroke="#565f89" stroke-width="1.5" stroke-dasharray="8,5" '
            f'style="animation-name:fadein;animation-duration:0.5s;"/>'
        )

    # Region labels
    region_labels = ""
    if len(vgs_vals) >= 2 and max(vgs_vals) > vth:
        t_lab = 0.5 + len(vgs_vals) * 0.5 + 0.3
        vds_mid_lin = (max(vgs_vals) - vth) * 0.4
        vds_mid_sat = vds_max * 0.7
        id_mid = id_max * 0.5
        lin_color = "#e0af68" if highlight == "linear" else "#565f89"
        sat_color = "#e0af68" if highlight == "saturation" else "#565f89"
        region_labels = (
            f'<text class="anim" data-start="{t_lab}" x="{px(vds_mid_lin):.1f}" y="{py(id_mid):.1f}" '
            f'fill="{lin_color}" font-size="15" text-anchor="middle" font-style="italic" '
            f'style="animation-name:fadein;animation-duration:0.4s;">Linear</text>'
            f'<text class="anim" data-start="{t_lab}" x="{px(vds_mid_sat):.1f}" y="{py(id_mid):.1f}" '
            f'fill="{sat_color}" font-size="15" text-anchor="middle" font-style="italic" '
            f'style="animation-name:fadein;animation-duration:0.4s;">Saturation</text>'
        )

    svg = (
        f'<svg width="{PW}" height="{PH}" style="position:absolute;left:50px;top:120px;">'
        f'{axes}{ticks}{curves_html}{sat_boundary}{region_labels}</svg>'
    )
    css = """
    h1.anim { animation-name: rise; animation-duration: 0.6s; font-size: 36px; }
    @keyframes rise   { 0%{opacity:0;transform:translateY(16px);} 100%{opacity:1;transform:translateY(0);} }
    @keyframes fadein { 0%{opacity:0;} 100%{opacity:1;} }
    """
    body = f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>{svg}'
    return _shell(body, css, index, total, citation)


def state_machine(scene, index, total):
    """Finite-state diagram: circles + directed arrows. Used for sequential logic, protocols, control units."""
    import math, html as _html
    title       = scene.get("title", "State Machine")
    citation    = scene.get("citation", "")
    states      = [s for s in (scene.get("states") or []) if isinstance(s, dict) and s.get("id")][:8]
    transitions = [t for t in (scene.get("transitions") or []) if isinstance(t, dict)][:12]
    initial_id  = str(scene.get("initial", ""))
    highlight_id = str(scene.get("highlight", ""))

    if not states:
        return title_bullets(scene, index, total)

    n = len(states)
    CX, CY, R = 580, 290, 200  # layout circle center and radius

    # Compute state positions on a circle
    pos = {}
    for si, st in enumerate(states):
        angle = -math.pi / 2 + 2 * math.pi * si / n
        px_s = CX + R * math.cos(angle)
        py_s = CY + R * math.sin(angle)
        pos[st["id"]] = (px_s, py_s)

    STATE_R = 42  # circle radius for each state node

    states_html = ""
    for si, st in enumerate(states):
        sid = st["id"]
        x, y = pos[sid]
        t_start = 0.3 + si * 0.2
        is_highlight = sid == highlight_id
        is_initial = sid == initial_id
        border_color = "#7aa2f7" if is_highlight else ("#9ece6a" if is_initial else "#565f89")
        glow = 'filter="url(#glow)"' if is_highlight else ""
        label = _html.escape(sid[:8])
        states_html += (
            f'<g class="anim" data-start="{t_start}" style="animation-name:scalein;animation-duration:0.4s;">'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{STATE_R}" fill="#1a1f2e" '
            f'stroke="{border_color}" stroke-width="2.5" {glow}/>'
            f'<text x="{x:.1f}" y="{y+6:.1f}" fill="{"#7aa2f7" if is_highlight else "#c0caf5"}" '
            f'font-size="{"14" if len(sid)>5 else "16"}" text-anchor="middle" font-weight="600">{label}</text>'
        )
        if is_initial:
            # Arrow pointing into initial state
            ix = x - STATE_R - 30
            states_html += (
                f'<line x1="{ix:.1f}" y1="{y:.1f}" x2="{x-STATE_R:.1f}" y2="{y:.1f}" '
                f'stroke="#9ece6a" stroke-width="2" marker-end="url(#arr)"/>'
            )
        states_html += '</g>'

    # Transitions
    trans_html = ""
    for ti, tr in enumerate(transitions):
        src, dst = tr.get("from", ""), tr.get("to", "")
        if src not in pos or dst not in pos:
            continue
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        label = _html.escape(str(tr.get("label", ""))[:20])
        t_start = 0.3 + n * 0.2 + ti * 0.25

        if src == dst:
            # Self-loop
            trans_html += (
                f'<g class="anim" data-start="{t_start}" style="animation-name:fadein;animation-duration:0.4s;">'
                f'<path d="M {x1+STATE_R*0.7:.1f} {y1-STATE_R*0.7:.1f} '
                f'C {x1+90:.1f} {y1-90:.1f} {x1+90:.1f} {y1+10:.1f} {x1+STATE_R:.1f} {y1:.1f}" '
                f'fill="none" stroke="#565f89" stroke-width="1.8" marker-end="url(#arr)"/>'
                f'<text x="{x1+80:.1f}" y="{y1-70:.1f}" fill="#8a8a8a" font-size="12">{label}</text>'
                f'</g>'
            )
        else:
            dx, dy = x2 - x1, y2 - y1
            dist = math.hypot(dx, dy)
            ux, uy = dx / dist, dy / dist
            # Slight curve
            mx = (x1 + x2) / 2 - uy * 25
            my = (y1 + y2) / 2 + ux * 25
            sx, sy = x1 + ux * STATE_R, y1 + uy * STATE_R
            ex2, ey2 = x2 - ux * STATE_R, y2 - uy * STATE_R
            trans_html += (
                f'<g class="anim" data-start="{t_start}" style="animation-name:fadein;animation-duration:0.4s;">'
                f'<path d="M {sx:.1f} {sy:.1f} Q {mx:.1f} {my:.1f} {ex2:.1f} {ey2:.1f}" '
                f'fill="none" stroke="#565f89" stroke-width="1.8" marker-end="url(#arr)"/>'
                f'<text x="{mx:.1f}" y="{my-8:.1f}" fill="#8a8a8a" font-size="13" text-anchor="middle">{label}</text>'
                f'</g>'
            )

    defs = (
        '<defs>'
        '<marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L8,3 Z" fill="#565f89"/></marker>'
        '<filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '</defs>'
    )
    svg = (
        f'<svg width="1100" height="560" style="position:absolute;left:0;top:120px;">'
        f'{defs}{trans_html}{states_html}</svg>'
    )
    css = """
    h1.anim { animation-name: rise; animation-duration: 0.6s; font-size: 38px; }
    @keyframes rise    { 0%{opacity:0;transform:translateY(16px);} 100%{opacity:1;transform:translateY(0);} }
    @keyframes fadein  { 0%{opacity:0;} 100%{opacity:1;} }
    @keyframes scalein { 0%{opacity:0;transform:scale(0.6);} 100%{opacity:1;transform:scale(1);} }
    """
    body = f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>{svg}'
    return _shell(body, css, index, total, citation)


TEMPLATES = {
    "title_bullets":   title_bullets,
    "formula_build":   formula_build,
    "flow":            flow,
    "compare":         compare,
    "circuit_flow":    circuit_flow,
    "waveform_plot":   waveform_plot,
    "pipeline_timing": pipeline_timing,
    "logic_truth":     logic_truth,
    "block_diagram":   block_diagram,
    "phasor_diagram":  phasor_diagram,
    "bode_plot":       bode_plot,
    "transistor_iv":   transistor_iv,
    "state_machine":   state_machine,
}


def render_scene_html(scene, index, total):
    visual = scene.get("visual") or {}
    vtype = visual.get("type", "title_bullets")
    merged = {**scene, **visual}
    fn = TEMPLATES.get(vtype, title_bullets)
    try:
        return fn(merged, index, total)
    except Exception:
        return title_bullets(merged, index, total)
