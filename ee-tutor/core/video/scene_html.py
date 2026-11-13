"""Rich HTML scene renderer for the agentic video system.

Takes a fully-specified AgentScene dict and returns an HTML page string
(1280×720) that the existing Playwright + ffmpeg pipeline can render.

Animation types supported:
  circuit_diagram    — SVG component chain with animated current dot
  device_cross_section — semiconductor layer diagram
  graph              — SVG plot from pre-computed xs/ys arrays
  equation_steps     — equations revealed line-by-line
  flow               — process boxes with arrows
  bullets            — text bullets  
  split_compare      — 2-3 column panels
  waveform           — waveform from xs/ys
"""
import html as _html
import math

from core.video.svg_components import render_component, wire, arrow, label_node
from core.video.templates import BASE_CSS


# ── Shell ────────────────────────────────────────────────────────────────────

def _shell(body: str, extra_css: str, index: int, total: int,
           citation: str, background_css: str = "") -> str:
    bg = background_css or "background:#181818;"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{BASE_CSS}
html, body {{ {bg} }}
{extra_css}
</style></head><body>
<div class="pad">
  <div class="idx">{index}/{total}</div>
  {body}
  <div class="cite">{_html.escape(citation)}</div>
</div>
</body></html>"""


def _bg_css(bg_spec: dict) -> str:
    """Convert a background_spec dict to a CSS background string."""
    if not bg_spec:
        return "background:#181818;"
    kind = bg_spec.get("kind", "solid")
    if kind == "gradient":
        c1 = bg_spec.get("color1", "#0d0f1a")
        c2 = bg_spec.get("color2", "#1a1f3a")
        angle = bg_spec.get("angle", 135)
        return f"background:linear-gradient({angle}deg,{c1},{c2});"
    if kind == "pattern":
        pat = bg_spec.get("pattern", "grid")
        if pat == "grid":
            return (
                "background:#111827;"
                "background-image:linear-gradient(rgba(122,162,247,0.07) 1px,transparent 1px),"
                "linear-gradient(90deg,rgba(122,162,247,0.07) 1px,transparent 1px);"
                "background-size:40px 40px;"
            )
        if pat == "blueprint":
            return (
                "background:#0a1628;"
                "background-image:linear-gradient(rgba(100,160,255,0.1) 1px,transparent 1px),"
                "linear-gradient(90deg,rgba(100,160,255,0.1) 1px,transparent 1px);"
                "background-size:30px 30px;"
            )
        if pat == "dots":
            return (
                "background:#12131f;"
                "background-image:radial-gradient(rgba(122,162,247,0.25) 1px,transparent 1px);"
                "background-size:24px 24px;"
            )
        return "background:#181818;"
    if kind == "image":
        path = bg_spec.get("path", "")
        if path:
            from pathlib import Path as _Path
            uri = _Path(path).as_uri()
            return f"background:url('{uri}') center/cover no-repeat; background-color:#0d0d0d;"
    return "background:#181818;"


# ── Animation types ───────────────────────────────────────────────────────────

def render_circuit_diagram(scene: dict, index: int, total: int) -> str:
    """Circuit component chain with animated current-dot."""
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    bg_spec  = scene.get("background_spec", {})
    spec     = scene.get("animation_spec", {})
    components = spec.get("components", [])   # list of {type, label}
    label_in  = spec.get("label_in", "Vin")
    label_out = spec.get("label_out", "Vout")

    if not components:
        return render_bullets(scene, index, total)

    n = len(components)
    BOX_W, GAP = 140, 70
    total_w = BOX_W * n + GAP * (n - 1)
    start_x = max(60, (1100 - total_w) // 2)
    CY = 320

    svgs = ""
    # Entry wire + label
    svgs += f'<line x1="{start_x-60}" y1="{CY}" x2="{start_x}" y2="{CY}" stroke="#c0caf5" stroke-width="2"/>'
    svgs += f'<text x="{start_x-65}" y="{CY+5}" fill="#9ece6a" font-size="14" text-anchor="end">{_html.escape(label_in)}</text>'

    for i, comp in enumerate(components):
        cx = start_x + i * (BOX_W + GAP) + BOX_W // 2
        ctype = str(comp.get("type", "R"))
        clabel = str(comp.get("label", ""))
        svgs += render_component(ctype, cx, CY, label=clabel, t_start=0.3 + i * 0.3)
        if i < n - 1:
            wx1 = cx + 30
            wx2 = start_x + (i + 1) * (BOX_W + GAP) - 30 + BOX_W // 2 - BOX_W // 2
            wx2 = start_x + (i + 1) * (BOX_W + GAP)
            svgs += wire(wx1, CY, wx2, CY, t_start=0.3 + i * 0.3 + 0.15)

    # Exit wire + label
    end_x = start_x + n * BOX_W + (n - 1) * GAP
    svgs += f'<line x1="{end_x}" y1="{CY}" x2="{end_x+60}" y2="{CY}" stroke="#c0caf5" stroke-width="2"/>'
    svgs += f'<text x="{end_x+65}" y="{CY+5}" fill="#9ece6a" font-size="14">{_html.escape(label_out)}</text>'

    # Animated current dot
    travel = max(total_w, 1)
    dot_start = 0.3 + n * 0.3 + 0.3
    svgs += (
        f'<circle class="anim" data-start="{dot_start}" cx="{start_x}" cy="{CY}" r="7"'
        f' fill="#ffb454" style="animation-name:travel_dot;animation-duration:{max(n*0.8,1.5):.1f}s;'
        f'animation-iteration-count:infinite;"/>'
    )
    extra_css = f"""
    h1.anim  {{ animation-name:rise;animation-duration:0.6s;font-size:38px; }}
    @keyframes rise       {{ 0%{{opacity:0;transform:translateY(16px);}} 100%{{opacity:1;transform:translateY(0);}} }}
    @keyframes fadein     {{ 0%{{opacity:0;}} 100%{{opacity:1;}} }}
    @keyframes travel_dot {{ 0%{{cx:{start_x};opacity:0.2;}} 5%{{opacity:1;}} 100%{{cx:{end_x};opacity:1;}} }}
    """
    body = (
        f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>'
        f'<svg width="1100" height="400" style="position:absolute;left:0;top:120px;">{svgs}</svg>'
    )
    return _shell(body, extra_css, index, total, citation, _bg_css(bg_spec))


def render_device_cross_section(scene: dict, index: int, total: int) -> str:
    """Semiconductor layer cross-section diagram (MOSFET, diode, BJT, etc.)."""
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    bg_spec  = scene.get("background_spec", {})
    spec     = scene.get("animation_spec", {})
    layers   = spec.get("layers", [])
    device   = spec.get("device", "MOSFET").upper()
    annotations = spec.get("annotations", [])  # list of {x,y,label,arrow_to}

    # Default MOSFET layers if none given
    if not layers:
        if device == "MOSFET":
            layers = [
                {"label": "Gate (Metal)", "color": "#7aa2f7", "height": 50},
                {"label": "Gate Oxide (SiO₂)", "color": "#e0af68", "height": 25},
                {"label": "Source (n+) | Channel (p) | Drain (n+)", "color": "#9ece6a", "height": 70},
                {"label": "p-Substrate", "color": "#565f89", "height": 100},
            ]
        elif device == "DIODE":
            layers = [
                {"label": "p-type (Anode)", "color": "#f7768e", "height": 100},
                {"label": "Depletion Region", "color": "#e0af68", "height": 30},
                {"label": "n-type (Cathode)", "color": "#7aa2f7", "height": 100},
            ]
        else:
            layers = [
                {"label": "Emitter (n+)", "color": "#9ece6a", "height": 60},
                {"label": "Base (p)", "color": "#e0af68", "height": 40},
                {"label": "Collector (n)", "color": "#7aa2f7", "height": 100},
            ]

    W = 700
    SX = (1100 - W) // 2
    SY = 160
    rects = ""
    total_h = sum(l.get("height", 60) for l in layers)
    y = SY
    for i, layer in enumerate(layers):
        h = layer.get("height", 60)
        color = layer.get("color", "#565f89")
        label = layer.get("label", "")
        t = 0.4 + i * 0.4
        rects += (
            f'<rect class="anim" data-start="{t}" x="{SX}" y="{y}" width="{W}" height="{h}"'
            f' fill="{color}" fill-opacity="0.25" stroke="{color}" stroke-width="1.5"'
            f' style="animation-name:slidein_left;animation-duration:0.5s;"/>'
            f'<text class="anim" data-start="{t+0.1}" x="{SX + W//2}" y="{y + h//2 + 6}"'
            f' fill="{color}" font-size="16" text-anchor="middle" font-weight="600"'
            f' style="animation-name:fadein;animation-duration:0.4s;">{_html.escape(label)}</text>'
        )
        y += h

    # Annotations (arrows + labels)
    ann_svg = ""
    for ai, ann in enumerate(annotations[:4]):
        ax, ay = float(ann.get("x", SX)), float(ann.get("y", SY))
        albl = str(ann.get("label", ""))
        ann_svg += (
            f'<g class="anim" data-start="{0.4 + len(layers)*0.4 + ai*0.3}"'
            f' style="animation-name:fadein;animation-duration:0.4s;">'
            f'<circle cx="{ax}" cy="{ay}" r="5" fill="#ffb454"/>'
            f'<text x="{ax+10}" y="{ay+5}" fill="#ffb454" font-size="13">{_html.escape(albl)}</text>'
            f'</g>'
        )

    extra_css = """
    h1.anim { animation-name:rise;animation-duration:0.6s;font-size:38px; }
    @keyframes rise         { 0%{opacity:0;transform:translateY(16px);} 100%{opacity:1;transform:translateY(0);} }
    @keyframes fadein       { 0%{opacity:0;} 100%{opacity:1;} }
    @keyframes slidein_left { 0%{opacity:0;transform:scaleX(0);transform-origin:left;} 100%{opacity:1;transform:scaleX(1);} }
    """
    body = (
        f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>'
        f'<svg width="1100" height="600" style="position:absolute;left:0;top:120px;">{rects}{ann_svg}</svg>'
    )
    return _shell(body, extra_css, index, total, citation, _bg_css(bg_spec))


def render_graph(scene: dict, index: int, total: int) -> str:
    """Plot curves from pre-computed xs/ys data arrays."""
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    bg_spec  = scene.get("background_spec", {})
    spec     = scene.get("animation_spec", {})
    curves   = spec.get("curves", [])    # list of {xs, ys, label, color}
    x_label  = str(spec.get("x_label", "x"))[:30]
    y_label  = str(spec.get("y_label", "y"))[:30]
    regions  = spec.get("regions", [])  # list of {x_start, x_end, label, color}
    op_point = spec.get("op_point")     # {x, y, label}

    if not curves:
        return render_bullets(scene, index, total)

    PW, PH = 950, 420
    ML, MR, MT, MB = 80, 30, 20, 60

    all_x = [v for c in curves for v in (c.get("xs") or [0, 1])]
    all_y = [v for c in curves for v in (c.get("ys") or [0, 1])]
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    if xmin == xmax: xmax = xmin + 1
    if ymin == ymax: ymax = ymin + 1

    def px(v): return ML + (v - xmin) / (xmax - xmin) * (PW - ML - MR)
    def py(v): return PH - MB - (v - ymin) / (ymax - ymin) * (PH - MT - MB)

    COLORS = ["#7aa2f7", "#9ece6a", "#e0af68", "#f7768e", "#bb9af7"]

    # Grid
    grid = ""
    for gv in [0.25, 0.5, 0.75]:
        gx = ML + gv * (PW - ML - MR)
        gy = MT + (1 - gv) * (PH - MT - MB)
        grid += f'<line x1="{gx:.1f}" y1="{MT}" x2="{gx:.1f}" y2="{PH-MB}" stroke="#222" stroke-width="1"/>'
        grid += f'<line x1="{ML}" y1="{gy:.1f}" x2="{PW-MR}" y2="{gy:.1f}" stroke="#222" stroke-width="1"/>'

    # Axes
    axes = (
        f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{PH-MB}" stroke="#555" stroke-width="2"/>'
        f'<line x1="{ML}" y1="{PH-MB}" x2="{PW-MR}" y2="{PH-MB}" stroke="#555" stroke-width="2"/>'
        f'<text x="{PW//2}" y="{PH}" fill="#888" font-size="13" text-anchor="middle">{_html.escape(x_label)}</text>'
        f'<text x="14" y="{PH//2}" fill="#888" font-size="13" text-anchor="middle" transform="rotate(-90,14,{PH//2})">{_html.escape(y_label)}</text>'
    )

    # Shaded regions
    region_svg = ""
    for ri, reg in enumerate(regions[:3]):
        rx1 = max(ML, px(float(reg.get("x_start", xmin))))
        rx2 = min(PW - MR, px(float(reg.get("x_end", xmax))))
        rcolor = str(reg.get("color", "#7aa2f7"))
        rlabel = str(reg.get("label", ""))
        t = 0.4 + ri * 0.2
        region_svg += (
            f'<rect class="anim" data-start="{t}" x="{rx1:.1f}" y="{MT}" '
            f'width="{max(0,rx2-rx1):.1f}" height="{PH-MT-MB}" fill="{rcolor}" fill-opacity="0.1"'
            f' style="animation-name:fadein;animation-duration:0.4s;"/>'
            f'<text class="anim" data-start="{t+0.1}" x="{(rx1+rx2)/2:.1f}" y="{MT+16}"'
            f' fill="{rcolor}" font-size="12" text-anchor="middle"'
            f' style="animation-name:fadein;animation-duration:0.4s;">{_html.escape(rlabel)}</text>'
        )

    # Curves
    curve_svg = ""
    legend_items = ""
    for ci, curve in enumerate(curves[:5]):
        xs = curve.get("xs") or []
        ys = curve.get("ys") or []
        if not xs or not ys:
            continue
        pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs, ys))
        color = str(curve.get("color", COLORS[ci % len(COLORS)]))
        clabel = str(curve.get("label", f"curve {ci+1}"))
        t = 0.6 + ci * 0.5

        # Total length estimate for dash animation
        seg_len = sum(
            math.hypot((px(xs[i+1]) - px(xs[i])), (py(ys[i+1]) - py(ys[i])))
            for i in range(len(xs)-1)
        ) if len(xs) > 1 else 500

        curve_svg += (
            f'<polyline class="anim" data-start="{t}" points="{pts}"'
            f' fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round"'
            f' stroke-dasharray="{seg_len:.0f}" '
            f' style="stroke-dashoffset:{seg_len:.0f};animation-name:drawcurve;animation-duration:1.5s;"/>'
        )
        legend_items += (
            f'<g class="anim" data-start="{t+0.5}" style="animation-name:fadein;animation-duration:0.4s;">'
            f'<line x1="0" y1="8" x2="20" y2="8" stroke="{color}" stroke-width="2.5"/>'
            f'<text x="25" y="12" fill="{color}" font-size="13">{_html.escape(clabel)}</text>'
            f'</g>'
        )

    # Operating point marker
    op_svg = ""
    if op_point:
        ox, oy = px(float(op_point.get("x", 0))), py(float(op_point.get("y", 0)))
        olabel = str(op_point.get("label", "Q"))
        t = 0.6 + len(curves) * 0.5 + 0.3
        op_svg = (
            f'<g class="anim" data-start="{t}" style="animation-name:fadein;animation-duration:0.5s;">'
            f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="8" fill="none" stroke="#f7768e" stroke-width="2"/>'
            f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="3" fill="#f7768e"/>'
            f'<text x="{ox+12:.1f}" y="{oy-8:.1f}" fill="#f7768e" font-size="13" font-weight="bold">{_html.escape(olabel)}</text>'
            f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{ox:.1f}" y2="{PH-MB}" stroke="#f7768e" stroke-width="1" stroke-dasharray="4,3"/>'
            f'<line x1="{ML}" y1="{oy:.1f}" x2="{ox:.1f}" y2="{oy:.1f}" stroke="#f7768e" stroke-width="1" stroke-dasharray="4,3"/>'
            f'</g>'
        )

    total_len_approx = 600
    extra_css = f"""
    h1.anim {{ animation-name:rise;animation-duration:0.6s;font-size:36px; }}
    @keyframes rise      {{ 0%{{opacity:0;transform:translateY(16px);}} 100%{{opacity:1;transform:translateY(0);}} }}
    @keyframes fadein    {{ 0%{{opacity:0;}} 100%{{opacity:1;}} }}
    @keyframes drawcurve {{ 0%{{stroke-dashoffset:{total_len_approx};}} 100%{{stroke-dashoffset:0;}} }}
    """
    legend = f'<svg width="250" height="{max(30, len(curves)*22)}" style="position:absolute;right:40px;top:150px;">{legend_items}</svg>'
    body = (
        f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>'
        f'<svg width="{PW}" height="{PH}" style="position:absolute;left:40px;top:140px;">'
        f'{grid}{region_svg}{axes}{curve_svg}{op_svg}</svg>'
        f'{legend}'
    )
    return _shell(body, extra_css, index, total, citation, _bg_css(bg_spec))


def render_equation_steps(scene: dict, index: int, total: int) -> str:
    """Equations revealed line-by-line with highlight on the active term."""
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    bg_spec  = scene.get("background_spec", {})
    spec     = scene.get("animation_spec", {})
    steps    = spec.get("steps", [])  # list of {equation, explanation}

    if not steps:
        return render_bullets(scene, index, total)

    lines_html = ""
    for i, step in enumerate(steps[:8]):
        eq   = _html.escape(str(step.get("equation", "")))
        expl = _html.escape(str(step.get("explanation", "")))
        t    = 0.5 + i * 0.8
        lines_html += (
            f'<div class="anim eq-row" data-start="{t}" style="animation-name:rise;animation-duration:0.5s;">'
            f'<div class="eq-formula">{eq}</div>'
            + (f'<div class="eq-expl">{expl}</div>' if expl else "")
            + f'</div>'
        )

    extra_css = """
    h1.anim  { animation-name:rise;animation-duration:0.6s;font-size:38px; }
    .eq-row  { opacity:0; margin:14px 0; display:flex; align-items:center; gap:28px; }
    .eq-formula { font-size:28px; font-family:monospace; color:#7aa2f7;
                  background:rgba(122,162,247,0.08); border-left:3px solid #7aa2f7;
                  padding:10px 20px; border-radius:0 8px 8px 0; min-width:340px; }
    .eq-expl { font-size:19px; color:#a9b8cc; flex:1; }
    @keyframes rise { 0%{opacity:0;transform:translateX(-20px);} 100%{opacity:1;transform:translateX(0);} }
    """
    body = (
        f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>'
        f'<div style="margin-top:30px;">{lines_html}</div>'
    )
    return _shell(body, extra_css, index, total, citation, _bg_css(bg_spec))


def render_flow(scene: dict, index: int, total: int) -> str:
    """Process boxes + arrows. Reuses existing flow template logic."""
    from core.video.templates import flow as _flow_tmpl
    merged = {**scene, **(scene.get("animation_spec") or {})}
    # Inject background_spec into extra_css via a wrapper
    base_html = _flow_tmpl(merged, index, total)
    return base_html  # background override not applied here (acceptable)


def render_bullets(scene: dict, index: int, total: int) -> str:
    """Rich bullet slide — richer than the base title_bullets."""
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    bg_spec  = scene.get("background_spec", {})
    spec     = scene.get("animation_spec", {})
    bullets  = spec.get("bullets") or scene.get("bullets", [])
    subtitle = str(spec.get("subtitle", ""))

    bullet_html = ""
    for i, b in enumerate(bullets[:6]):
        t = 0.6 + i * 0.5
        bullet_html += (
            f'<div class="anim bullet" data-start="{t}" style="animation-name:rise;animation-duration:0.5s;">'
            f'<span class="bullet-dot">▶</span>'
            f'<span class="bullet-text">{_html.escape(str(b))}</span>'
            f'</div>'
        )
    sub_html = f'<p class="anim subtitle" data-start="0.3" style="animation-name:fadein;animation-duration:0.5s;">{_html.escape(subtitle)}</p>' if subtitle else ""

    extra_css = """
    h1.anim  { animation-name:rise;animation-duration:0.6s;font-size:42px; }
    .subtitle { font-size:22px; color:#8a8a9a; margin-bottom:24px; }
    .bullet  { opacity:0; display:flex; align-items:flex-start; gap:16px;
               margin:12px 0; font-size:26px; line-height:1.5; }
    .bullet-dot  { color:#7aa2f7; font-size:18px; margin-top:4px; flex-shrink:0; }
    .bullet-text { color:#d4d8f0; }
    @keyframes rise   { 0%{opacity:0;transform:translateY(18px);} 100%{opacity:1;transform:translateY(0);} }
    @keyframes fadein { 0%{opacity:0;} 100%{opacity:1;} }
    """
    body = (
        f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>'
        f'{sub_html}'
        f'<div style="margin-top:16px;">{bullet_html}</div>'
    )
    return _shell(body, extra_css, index, total, citation, _bg_css(bg_spec))


def render_split_compare(scene: dict, index: int, total: int) -> str:
    """2-3 column side-by-side comparison panels."""
    title    = scene.get("title", "")
    citation = scene.get("citation", "")
    bg_spec  = scene.get("background_spec", {})
    spec     = scene.get("animation_spec", {})
    panels   = spec.get("panels", [])  # list of {label, points, color}

    if not panels:
        return render_bullets(scene, index, total)

    n = min(len(panels), 3)
    PANEL_COLORS = ["#7aa2f7", "#9ece6a", "#e0af68"]
    cols_html = ""
    for i, panel in enumerate(panels[:3]):
        color = str(panel.get("color", PANEL_COLORS[i % len(PANEL_COLORS)]))
        plabel = _html.escape(str(panel.get("label", f"Option {i+1}")))
        points = [str(p) for p in (panel.get("points") or [])][:5]
        pts_html = "".join(f'<li>{_html.escape(p)}</li>' for p in points)
        t = 0.5 + i * 0.4
        cols_html += (
            f'<div class="anim panel" data-start="{t}"'
            f' style="animation-name:slidein;animation-duration:0.5s;border-top:3px solid {color};">'
            f'<div class="panel-head" style="color:{color};">{plabel}</div>'
            f'<ul>{pts_html}</ul>'
            f'</div>'
        )

    extra_css = """
    h1.anim { animation-name:rise;animation-duration:0.6s;font-size:38px; }
    .panels { display:flex; gap:28px; margin-top:30px; }
    .panel  { opacity:0; flex:1; background:rgba(255,255,255,0.04); border-radius:12px;
               padding:24px 22px; }
    .panel-head { font-size:22px; font-weight:700; margin-bottom:14px; }
    .panel ul   { list-style:none; font-size:19px; line-height:1.8; color:#c0caf5; }
    .panel li   { padding-left:18px; position:relative; }
    .panel li::before { content:"•"; position:absolute; left:0; color:#565f89; }
    @keyframes rise    { 0%{opacity:0;transform:translateY(16px);} 100%{opacity:1;transform:translateY(0);} }
    @keyframes fadein  { 0%{opacity:0;} 100%{opacity:1;} }
    @keyframes slidein { 0%{opacity:0;transform:translateX(20px);} 100%{opacity:1;transform:translateX(0);} }
    """
    body = (
        f'<h1 class="anim" data-start="0">{_html.escape(title)}</h1>'
        f'<div class="panels">{cols_html}</div>'
    )
    return _shell(body, extra_css, index, total, citation, _bg_css(bg_spec))


# ── Dispatcher ────────────────────────────────────────────────────────────────

AGENT_RENDERERS = {
    "circuit_diagram":      render_circuit_diagram,
    "device_cross_section": render_device_cross_section,
    "graph":                render_graph,
    "equation_steps":       render_equation_steps,
    "flow":                 render_flow,
    "bullets":              render_bullets,
    "split_compare":        render_split_compare,
    "waveform":             render_graph,  # reuse graph renderer
}


def render_agent_scene_html(scene: dict, index: int, total: int) -> str:
    """Render an agent-produced scene to HTML. Falls back to bullets on error."""
    atype = str((scene.get("animation_spec") or {}).get("type", "bullets"))
    fn = AGENT_RENDERERS.get(atype, render_bullets)
    try:
        return fn(scene, index, total)
    except Exception as e:
        # graceful fallback
        fallback = {**scene, "animation_spec": {"type": "bullets", "bullets": [str(e)]}}
        return render_bullets(fallback, index, total)
