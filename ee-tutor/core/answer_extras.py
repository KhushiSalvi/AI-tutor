"""Extras for richer answers: (1) clean_extras() tidies the optional interactive parts of a model
answer; (2) search_images() finds credited diagram images on Wikimedia Commons (no API key).

Original note for clean_extras: cleans the optional 'interactive' parts of a model answer (mind map, steps, example,
summary, follow-up questions) so a malformed or oversized model reply can never break the UI."""
import re

import requests


def strip_citations(text):
    if not text:
        return ""
    text = re.sub(r"\s*\[(?:\s*p\.?\s*\d+|\d+(?:\s*,\s*\d+)*|W\d+)\s*\]", "", str(text))
    return re.sub(r" +", " ", text).strip()


def _s(x, n):
    return strip_citations(x)[:n] if x is not None else ""


def _list(x):
    return x if isinstance(x, list) else []


# ---------- flowchart: model gives nodes/edges, WE write the Mermaid code (so it can't be malformed) ----------
_SHAPES = {"decision": ('{"', '"}'), "round": ('("', '")'), "box": ('["', '"]')}


def _label(x, n=48):
    s = re.sub(r'["\[\]{}()|`;\\]', " ", str(x or ""))      # characters Mermaid treats as syntax
    s = re.sub(r"\s+", " ", s).strip()[:n]
    return s.replace("<", "#lt;").replace(">", "#gt;")        # entity codes, added last so they survive


def clean_flowchart(f):
    """{"direction", "nodes":[{"id","label","shape"}], "edges":[{"from","to","label"}]} -> Mermaid text or None."""
    if not isinstance(f, dict):
        return None
    ids, lines = {}, []
    for n in _list(f.get("nodes"))[:12]:
        if not isinstance(n, dict):
            continue
        key, label = str(n.get("id", "")).strip(), _label(n.get("label"))
        if key and label and key not in ids:
            l, r = _SHAPES.get(n.get("shape"), _SHAPES["box"])
            ids[key] = f"n{len(ids)}"
            lines.append(f"    {ids[key]}{l}{label}{r}")
    edges = []
    for e in _list(f.get("edges"))[:16]:
        if not isinstance(e, dict):
            continue
        a, b = ids.get(str(e.get("from", "")).strip()), ids.get(str(e.get("to", "")).strip())
        if a and b and a != b:
            lab = _label(e.get("label"), 24)
            edges.append(f"    {a} -->|{lab}| {b}" if lab else f"    {a} --> {b}")
    if len(ids) < 3 or len(edges) < 2:
        return None
    return "flowchart " + ("LR" if f.get("direction") == "LR" else "TD") + "\n" + "\n".join(lines + edges)


def clean_extras(d):
    out = {"mindmap": None, "flowchart": None, "steps": [], "example": "", "summary": [], "followups": []}

    m = d.get("mindmap")
    if isinstance(m, dict):
        branches = []
        for b in _list(m.get("branches"))[:5]:
            if isinstance(b, dict) and _s(b.get("label"), 40):
                kids = [_s(k, 60) for k in _list(b.get("children"))[:3] if _s(k, 60)]
                branches.append({"label": _s(b["label"], 40), "children": kids})
        if _s(m.get("center"), 40) and len(branches) >= 2:
            out["mindmap"] = {"center": _s(m["center"], 40), "branches": branches}

    out["flowchart"] = clean_flowchart(d.get("flowchart"))
    out["steps"] = [_s(x, 160) for x in _list(d.get("steps"))[:6] if _s(x, 160)]
    out["example"] = _s(d.get("example"), 400)
    out["summary"] = [_s(x, 160) for x in _list(d.get("summary"))[:4] if _s(x, 160)]
    out["followups"] = [_s(x, 100) for x in _list(d.get("followups"))[:3] if _s(x, 100)]
    return out


# ---------- images from the web (Wikimedia Commons) ----------

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "EE-Tutor/1.0 (student project; contact via GitHub)"}
BAD = re.compile(r"logo|icon|flag|portrait|signature|stamp|coat of arms|\.pdf|\.djvu", re.I)
OK_MIME = {"image/svg+xml", "image/png", "image/jpeg"}
_cache = {}


def _plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()[:60]


def search_images(q, n=3, timeout=6):
    q = (q or "").strip()[:120]
    if not q:
        return []
    key = q.lower()
    if key in _cache:
        return _cache[key]
    out = []
    try:
        r = requests.get(
            API,
            params={
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": f"{q} diagram filetype:bitmap|drawing", "gsrnamespace": 6, "gsrlimit": 15,
                "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 700,
            },
            headers=HEADERS, timeout=timeout,
        )
        r.raise_for_status()
        pages = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        for p in pages:
            info = (p.get("imageinfo") or [{}])[0]
            title = p.get("title", "").replace("File:", "")
            if info.get("mime") not in OK_MIME or (info.get("width") or 0) < 300 or BAD.search(title):
                continue
            meta = info.get("extmetadata") or {}
            out.append({
                "thumb": info.get("thumburl") or info.get("url"),
                "url": info.get("url"),
                "page": info.get("descriptionurl"),
                "title": re.sub(r"\.\w+$", "", title).replace("_", " ")[:80],
                "credit": _plain((meta.get("Artist") or {}).get("value")),
                "license": _plain((meta.get("LicenseShortName") or {}).get("value")),
            })
            if len(out) >= n:
                break
    except Exception:
        return []  # never break an answer because images failed
    _cache[key] = out
    return out
