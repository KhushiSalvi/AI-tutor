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


TEMPLATES = {
    "title_bullets": title_bullets,
    "formula_build": formula_build,
    "flow": flow,
    "compare": compare,
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
