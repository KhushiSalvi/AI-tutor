"""Find the NPTEL lecture clip that best teaches a topic.

Transcripts live in data/nptel/*.jsonl (written by core/nptel/ingest.py): one ~75 s window per line,
{"video_id", "title", "course", "start", "end", "text"}.

How a clip is chosen (works for any topic, nothing is hard-coded to one subject):
  1. CANDIDATES  - every window is scored two ways and the rankings are fused:
                   words (BM25, tolerant of caption quirks such as "p n junction") and meaning
                   (the same BGE embedding model the tutor already uses, cached in data/nptel_emb/).
                   A lecture whose title matches the topic gets a bonus.
  2. JUDGE       - Gemini reads the best few candidates and picks the one where the lecturer is
                   actually TEACHING the topic. It rejects passing mentions, recaps, "next class"
                   teasers and related-but-different topics, and may answer "none".
  3. FALLBACK    - if the judge is unavailable (no key, quota, offline) the top fused candidate is used,
                   after a recap/opening/closing penalty and a minimum-coverage check.
Debug any query:   python -m core.nptel.search "explain the diode"
"""
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path("data/nptel")
EMB_DIR = Path("data/nptel_emb")
EMB_MODEL = os.environ.get("NPTEL_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
N_CANDIDATES = 8        # how many clips the judge gets to see
MAX_PER_LECTURE = 2

STOP = set("""a an the and or of to in on for with is are was were be been it its this that these those as at by from into
than then so such can may will would should how what why when which who whom whose do does did done not no yes you your we
our they their them i me my he she his her about explain explained explanation tell teach show give make video lecture
lectures class topic concept please also more most very just like using use used between over under again each other some
any all complete deeply detail detailed work works working""".split())

RECAP = re.compile(r"\b(next (class|lecture|session|video)|last (class|lecture|time)|previous (class|lecture)|"
                   r"so far we|in this lecture we (will|shall)|today we (will|shall)|we will (see|discuss|study|look) .{0,30}(next|later)|"
                   r"to summari[sz]e|in summary|let us recap|let us summari[sz]e)\b")

_cache = {"stamp": None, "segs": [], "df": Counter(), "avgdl": 1.0, "videos": {}, "emb": None}
_model = None
_warned = set()
_results = {}


def _warn(key, msg):
    if key not in _warned:
        _warned.add(key)
        print("[nptel]", msg, file=sys.stderr)


# ---------------------------------------------------------------- text helpers
def _norm(text):
    """Make caption quirks comparable: 'p-n' / 'p n' -> 'pn', 'n p n' -> 'npn', 'r l c' -> 'rlc'."""
    t = (text or "").lower()
    t = re.sub(r"\b([b-hj-z])-(?=[b-hj-z]\b)", r"\1 ", t)
    return re.sub(r"\b[b-hj-z](?:\s+[b-hj-z]\b)+", lambda m: re.sub(r"\s+", "", m.group(0)), t)


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("sses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    for suf in ("ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def tokens(text):
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", _norm(text)) if w not in STOP and len(w) > 1]


def _mmss(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


# ---------------------------------------------------------------- loading + embeddings
def _embedder():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMB_MODEL)
    return _model


def _file_embeddings(f, texts):
    """Embeddings for one lecture file, cached next to the data and rebuilt only if the file changed."""
    import numpy as np
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    npy = EMB_DIR / (f.stem + ".npy")
    if npy.exists() and npy.stat().st_mtime >= f.stat().st_mtime:
        arr = np.load(npy)
        if arr.shape[0] == len(texts):
            return arr
    arr = _embedder().encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    np.save(npy, arr)
    return arr


def _load():
    files = sorted(DATA.glob("*.jsonl")) if DATA.exists() else []
    stamp = tuple((f.name, f.stat().st_mtime_ns) for f in files)
    if stamp == _cache["stamp"]:
        return _cache
    segs, df, videos, per_file = [], Counter(), defaultdict(list), []
    for f in files:
        rows = []
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                s = json.loads(line)
            except ValueError:
                continue
            toks = tokens(s.get("text", ""))
            s["_tf"], s["_len"] = Counter(toks), len(toks)
            s["_recap"] = bool(RECAP.search(s.get("text", "").lower()))
            s["_i"] = len(segs)
            segs.append(s)
            rows.append(s)
            df.update(s["_tf"].keys())
            videos[s["video_id"]].append(s)
        per_file.append((f, rows))
    for v in videos.values():
        v.sort(key=lambda x: x["start"])
    avgdl = (sum(s["_len"] for s in segs) / len(segs)) if segs else 1.0

    emb = None
    if segs:
        try:
            import numpy as np
            parts = [_file_embeddings(f, [r["text"] for r in rows]) for f, rows in per_file if rows]
            emb = np.vstack(parts)
        except Exception as e:
            _warn("emb", f"meaning-based matching is off ({type(e).__name__}: {str(e)[:100]}); using words only")
    _cache.update(stamp=stamp, segs=segs, df=df, avgdl=max(avgdl, 1.0), videos=dict(videos), emb=emb)
    _results.clear()
    return _cache


# ---------------------------------------------------------------- scoring
def _lexical(c, mult):
    n, k1, b = len(c["segs"]), 1.5, 0.75
    max_idf = math.log(1 + (n + 0.5) / 1.5)

    def idf(t):
        d = c["df"].get(t, 0)
        return math.log(1 + (n - d + 0.5) / (d + 0.5)) if d else 0.7 * max_idf

    weight = {t: idf(t) * m for t, m in mult.items()}
    scores = []
    for s in c["segs"]:
        sc = 0.0
        for t, w in weight.items():
            tf = s["_tf"].get(t)
            if tf:
                sc += w * tf * (k1 + 1) / (tf + k1 * (1 - b + b * s["_len"] / c["avgdl"]))
        scores.append(sc)
    return scores, idf


def _dense(c, query):
    if c["emb"] is None:
        return None
    try:
        q = _embedder().encode([QUERY_PREFIX + query], normalize_embeddings=True)[0]
        return (c["emb"] @ q).tolist()
    except Exception as e:
        _warn("dense", f"meaning-based matching failed ({type(e).__name__}); using words only")
        return None


def _ranks(scores, only_positive=False):
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return {i: r for r, i in enumerate(order) if not (only_positive and scores[i] <= 0)}


def _candidates(c, query, extra):
    mult = {}
    for t in tokens(query):
        mult[t] = 3.0
    for t in tokens(extra):
        mult.setdefault(t, 1.0)
    if not mult:
        return [], {}
    q_terms = set(tokens(query)) or set(mult)
    lex, idf = _lexical(c, mult)
    den = _dense(c, query)

    rl = _ranks(lex, only_positive=True)
    rd = _ranks(den) if den is not None else {}
    q_total = sum(idf(t) for t in q_terms) or 1.0

    title_bonus = {}
    cover = {}
    for vid, wins in c["videos"].items():
        title = set(tokens(wins[0].get("title", "")))
        title_bonus[vid] = 0.02 * sum(idf(t) for t in q_terms if t in title) / q_total
        seen = set()
        for s in wins:
            seen.update(t for t in q_terms if t in s["_tf"])
        cover[vid] = sum(idf(t) for t in seen) / q_total

    fused = {}
    for s in c["segs"]:
        i = s["_i"]
        sc = (1 / (60 + rl[i]) if i in rl else 0.0) + (1 / (60 + rd[i]) if i in rd else 0.0)
        if sc <= 0:
            continue
        sc += title_bonus[s["video_id"]]
        length = c["videos"][s["video_id"]][-1]["end"]
        if s["_recap"]:
            sc *= 0.5
        if s["start"] > length - 240:
            sc *= 0.6
        if s["start"] < 45:
            sc *= 0.7
        fused[i] = sc

    picked, per_video = [], Counter()
    for i in sorted(fused, key=fused.get, reverse=True):
        s = c["segs"][i]
        v = s["video_id"]
        if per_video[v] >= MAX_PER_LECTURE:
            continue
        if any(p["video_id"] == v and abs(p["start"] - s["start"]) < 90 for p in picked):
            continue                                   # overlapping window of a clip already chosen
        s["_fused"], s["_cover"] = fused[i], cover[v]
        s["_dense"] = den[i] if den is not None else None
        picked.append(s)
        per_video[v] += 1
        if len(picked) >= N_CANDIDATES:
            break
    return picked, cover


# ---------------------------------------------------------------- AI judge
JUDGE_SYSTEM = (
    "You help a student find the part of a lecture video that explains a topic. You get the topic and numbered "
    "candidate clips taken from lecture transcripts (automatic captions, so spelling and punctuation may be off). "
    "Pick the ONE clip where the lecturer is actually teaching or explaining the topic itself. Reject clips that only "
    "mention it in passing, recap earlier lectures, preview the next class, or cover a related but different topic "
    "(for example 'diode connected MOSFET' is not the diode). If several clips from one lecture teach it, prefer the "
    "one where the explanation starts. If no candidate really teaches the topic, answer null. "
    'Return ONLY JSON: {"best": <candidate number or null>, "reason": "<one short sentence>"}'
)


def _judge(query, cands):
    """-> (index into cands | None, ok). ok=False means the judge could not be used."""
    try:
        from core.llm import generate
    except Exception:
        return None, False
    lines = [f"Topic: {query.strip()[:300]}", "", "Candidates:"]
    for n, s in enumerate(cands, 1):
        lines.append(f"[{n}] Lecture: {s.get('title', '')[:90]} (at {_mmss(s['start'])})\n{s['text'][:420]}")
    try:
        raw = generate(JUDGE_SYSTEM, "\n".join(lines))
        m = re.search(r"\{.*\}", raw or "", re.S)
        best = json.loads(m.group(0)).get("best")
    except Exception as e:
        _warn("judge", f"AI check skipped ({type(e).__name__}: {str(e)[:80]}); using the top match")
        return None, False
    if best is None:
        return None, True
    try:
        k = int(best)
    except (TypeError, ValueError):
        return None, False
    return (k - 1, True) if 1 <= k <= len(cands) else (None, False)


# ---------------------------------------------------------------- public API
def find_clip(query, extra="", clip_len=90, debug=False):
    """Best clip for the user's question `query` (lesson-plan words in `extra` only help candidate search).
    Returns None when nothing in data/nptel really teaches the topic."""
    c = _load()
    if not c["segs"] or not (query or "").strip():
        return None
    key = (query.strip().lower(), (extra or "").strip().lower(), clip_len)
    if key in _results and not debug:
        return _results[key]

    cands, _ = _candidates(c, query, extra)
    pick, method = None, "none"
    if cands:
        idx, ok = _judge(query, cands)
        if ok:
            pick, method = (cands[idx] if idx is not None else None), "ai"
        else:
            best = cands[0]
            if best["_cover"] >= 0.34:               # fallback: the lecture must cover most of what was asked
                pick, method = best, "fallback"
    if debug:
        print(f"\nQuery: {query!r}   ({len(c['segs'])} windows, meaning-search {'on' if c['emb'] is not None else 'off'})")
        for n, s in enumerate(cands, 1):
            d = "" if s["_dense"] is None else f" sim={s['_dense']:.2f}"
            mark = "  <== chosen" if s is pick else ""
            print(f" [{n}] {s['title'][:55]} @ {_mmss(s['start'])}  fused={s['_fused']:.4f} cover={s['_cover']:.2f}{d}{mark}")
        print(" method:", method)

    out = None
    if pick is not None:
        start = max(0.0, pick["start"] - 2)
        text = pick["text"]
        out = {
            "video_id": pick["video_id"], "title": pick.get("title", ""), "course": pick.get("course", ""),
            "start": round(start, 1), "end": round(start + clip_len, 1),
            "snippet": (text[:150].rsplit(" ", 1)[0] + "…") if len(text) > 150 else text,
            "score": round(pick["_fused"], 4), "method": method,
        }
    _results[key] = out
    return out


if __name__ == "__main__":
    for q in sys.argv[1:] or ["explain the diode"]:
        r = find_clip(q, debug=True)
        print(" result:", r and f"{r['title']} @ {_mmss(r['start'])}  https://youtu.be/{r['video_id']}?t={int(r['start'])}")
