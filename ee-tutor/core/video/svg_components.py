"""SVG circuit component library for the circuit_diagram animation type.

Every component returns an SVG string fragment.  The layout engine in
scene_html.py places components along a path and connects them with wires.
All coordinates are in the local component space (40x80 bounding box by
default) and are scaled/translated by the caller.
"""
import html
import math


# ── helpers ──────────────────────────────────────────────────────────────────

def _g(content: str, transform: str = "", cls: str = "", data_start: float = 0,
       anim: str = "fadein", dur: float = 0.4) -> str:
    t = f' transform="{transform}"' if transform else ""
    c = f' class="anim {cls}"' if cls else ' class="anim"'
    return (
        f'<g{c} data-start="{data_start:.2f}"'
        f' style="animation-name:{anim};animation-duration:{dur}s;"{t}>'
        f'{content}</g>'
    )


def _text(x, y, label, size=13, color="#c0caf5", anchor="middle", bold=False):
    fw = "bold" if bold else "normal"
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}"'
        f' font-weight="{fw}" fill="{color}">{html.escape(str(label))}</text>'
    )


# ── components ────────────────────────────────────────────────────────────────

def resistor(x: float, y: float, label: str = "", t_start: float = 0) -> str:
    """Zigzag resistor at (x,y). Leads extend left/right to x±30."""
    body = (
        # left wire
        f'<line x1="{x-30}" y1="{y}" x2="{x-12}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
        # zigzag
        f'<polyline points="{x-12},{y} {x-9},{y-10} {x-3},{y+10} {x+3},{y-10} {x+9},{y+10} {x+12},{y}"'
        f' fill="none" stroke="#7aa2f7" stroke-width="2.5" stroke-linejoin="round"/>'
        # right wire
        f'<line x1="{x+12}" y1="{y}" x2="{x+30}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
    )
    lbl = _text(x, y - 18, label, size=12, color="#9ece6a") if label else ""
    return _g(body + lbl, data_start=t_start)


def capacitor(x: float, y: float, label: str = "", t_start: float = 0) -> str:
    """Parallel-plate capacitor at (x,y)."""
    body = (
        f'<line x1="{x-30}" y1="{y}" x2="{x-5}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
        f'<line x1="{x-5}" y1="{y-14}" x2="{x-5}" y2="{y+14}" stroke="#7aa2f7" stroke-width="3"/>'
        f'<line x1="{x+5}" y1="{y-14}" x2="{x+5}" y2="{y+14}" stroke="#7aa2f7" stroke-width="3"/>'
        f'<line x1="{x+5}" y1="{y}" x2="{x+30}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
    )
    lbl = _text(x, y - 22, label, size=12, color="#9ece6a") if label else ""
    return _g(body + lbl, data_start=t_start)


def inductor(x: float, y: float, label: str = "", t_start: float = 0) -> str:
    """Series of bumps for inductor."""
    n_bumps = 4
    bump_w = 10
    total_w = n_bumps * bump_w
    bx = x - total_w / 2
    arcs = ""
    for i in range(n_bumps):
        cx_ = bx + i * bump_w + bump_w / 2
        arcs += (
            f'<path d="M {bx + i*bump_w} {y} A {bump_w/2} {bump_w/2} 0 0 1 {bx+(i+1)*bump_w} {y}"'
            f' fill="none" stroke="#e0af68" stroke-width="2.5"/>'
        )
    body = (
        f'<line x1="{x-30}" y1="{y}" x2="{bx}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
        + arcs +
        f'<line x1="{bx+total_w}" y1="{y}" x2="{x+30}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
    )
    lbl = _text(x, y - 18, label, size=12, color="#9ece6a") if label else ""
    return _g(body + lbl, data_start=t_start)


def diode(x: float, y: float, label: str = "", t_start: float = 0) -> str:
    """Diode (anode left, cathode right)."""
    body = (
        f'<line x1="{x-30}" y1="{y}" x2="{x-10}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
        f'<polygon points="{x-10},{y-11} {x-10},{y+11} {x+10},{y}" fill="#f7768e"/>'
        f'<line x1="{x+10}" y1="{y-12}" x2="{x+10}" y2="{y+12}" stroke="#c0caf5" stroke-width="2.5"/>'
        f'<line x1="{x+10}" y1="{y}" x2="{x+30}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
    )
    lbl = _text(x, y - 20, label, size=12, color="#9ece6a") if label else ""
    return _g(body + lbl, data_start=t_start)


def voltage_source(x: float, y: float, label: str = "Vs", t_start: float = 0) -> str:
    """Circle voltage source."""
    r = 18
    body = (
        f'<line x1="{x-30}" y1="{y}" x2="{x-r}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#1a1f2e" stroke="#9ece6a" stroke-width="2"/>'
        f'<text x="{x-6}" y="{y+5}" font-size="14" fill="#9ece6a" text-anchor="middle">+</text>'
        f'<text x="{x+8}" y="{y+5}" font-size="14" fill="#9ece6a" text-anchor="middle">−</text>'
        f'<line x1="{x+r}" y1="{y}" x2="{x+30}" y2="{y}" stroke="#c0caf5" stroke-width="2"/>'
    )
    lbl = _text(x, y - r - 6, label, size=12, color="#9ece6a") if label else ""
    return _g(body + lbl, data_start=t_start)


def ground(x: float, y: float, t_start: float = 0) -> str:
    """Ground symbol (three horizontal lines)."""
    body = (
        f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y+10}" stroke="#c0caf5" stroke-width="2"/>'
        f'<line x1="{x-14}" y1="{y+10}" x2="{x+14}" y2="{y+10}" stroke="#c0caf5" stroke-width="2.5"/>'
        f'<line x1="{x-9}" y1="{y+16}" x2="{x+9}" y2="{y+16}" stroke="#c0caf5" stroke-width="2"/>'
        f'<line x1="{x-4}" y1="{y+22}" x2="{x+4}" y2="{y+22}" stroke="#c0caf5" stroke-width="1.5"/>'
    )
    return _g(body, data_start=t_start)


def mosfet_n(x: float, y: float, label: str = "M", t_start: float = 0) -> str:
    """N-channel MOSFET symbol (gate left, drain top, source bottom)."""
    # Gate line
    gx, gy = x - 20, y
    # Body
    body = (
        # gate lead
        f'<line x1="{gx-20}" y1="{gy}" x2="{gx}" y2="{gy}" stroke="#c0caf5" stroke-width="2"/>'
        # gate bar
        f'<line x1="{gx}" y1="{gy-18}" x2="{gx}" y2="{gy+18}" stroke="#7aa2f7" stroke-width="3"/>'
        # channel (dashed)
        f'<line x1="{gx+6}" y1="{gy-18}" x2="{gx+6}" y2="{gy+18}" stroke="#c0caf5" stroke-width="1.5" stroke-dasharray="4,3"/>'
        # drain
        f'<line x1="{gx+6}" y1="{gy-18}" x2="{gx+6}" y2="{gy-12}"  stroke="#c0caf5" stroke-width="2"/>'
        f'<line x1="{gx+6}" y1="{gy-12}" x2="{x+30}" y2="{gy-12}" stroke="#c0caf5" stroke-width="2"/>'
        # source
        f'<line x1="{gx+6}" y1="{gy+18}" x2="{gx+6}" y2="{gy+12}"  stroke="#c0caf5" stroke-width="2"/>'
        f'<line x1="{gx+6}" y1="{gy+12}" x2="{x+30}" y2="{gy+12}" stroke="#c0caf5" stroke-width="2"/>'
        # arrow on source
        f'<polygon points="{gx+6},{gy+12} {gx+2},{gy+6} {gx+10},{gy+6}" fill="#c0caf5"/>'
    )
    lbl = _text(x + 10, y - 28, label, size=12, color="#bb9af7", bold=True) if label else ""
    return _g(body + lbl, data_start=t_start)


def wire(x1: float, y1: float, x2: float, y2: float, t_start: float = 0,
         color: str = "#c0caf5") -> str:
    """A simple wire segment."""
    body = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"/>'
    return _g(body, data_start=t_start)


def arrow(x1: float, y1: float, x2: float, y2: float, label: str = "",
          t_start: float = 0, color: str = "#ffb454") -> str:
    """Arrow with optional label."""
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1
    ux, uy = dx / dist, dy / dist
    # arrowhead
    hlen = 12
    ax1 = x2 - hlen * (ux - 0.4 * uy)
    ay1 = y2 - hlen * (uy + 0.4 * ux)
    ax2 = x2 - hlen * (ux + 0.4 * uy)
    ay2 = y2 - hlen * (uy - 0.4 * ux)
    body = (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"'
        f' stroke="{color}" stroke-width="2.5"/>'
        f'<polygon points="{x2:.1f},{y2:.1f} {ax1:.1f},{ay1:.1f} {ax2:.1f},{ay2:.1f}" fill="{color}"/>'
    )
    if label:
        mx, my = (x1 + x2) / 2 - 12 * uy, (y1 + y2) / 2 + 12 * ux
        body += _text(mx, my, label, size=12, color=color)
    return _g(body, data_start=t_start)


def label_node(x: float, y: float, text: str, t_start: float = 0,
               color: str = "#e0af68") -> str:
    body = (
        f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>'
        + _text(x + 8, y + 5, text, size=13, color=color, anchor="start")
    )
    return _g(body, data_start=t_start)


# ── component lookup ──────────────────────────────────────────────────────────

COMPONENT_FNS = {
    "R": resistor, "resistor": resistor,
    "C": capacitor, "capacitor": capacitor,
    "L": inductor, "inductor": inductor,
    "D": diode, "diode": diode,
    "V": voltage_source, "source": voltage_source, "vsource": voltage_source,
    "GND": ground, "ground": ground,
    "M": mosfet_n, "MOSFET": mosfet_n, "mosfet": mosfet_n, "nmos": mosfet_n,
}


def render_component(ctype: str, x: float, y: float, label: str = "",
                     t_start: float = 0) -> str:
    fn = COMPONENT_FNS.get(ctype, resistor)
    if ctype in ("GND", "ground"):
        return fn(x, y, t_start=t_start)
    return fn(x, y, label=label, t_start=t_start)
