"""Tutor logic without any UI. Used by api.py (moved out of the old Streamlit app.py)."""
import json
import os
import re
import subprocess
import sys
import threading
from functools import lru_cache
from pathlib import Path

import pymupdf

from core.llm import generate, llm_ready
from core.retrieval.hybrid import Retriever
from core.web_search import web_search, grounded_answer
from core.answer_extras import clean_extras
from core.video.lesson_plan import build_video_prompt, estimate_seconds, trim_to_budget, sanitize_scenes, MAX_SECONDS
from core.video.animate import build_video

# printed page = PDF page - offset.
# Manual overrides here take priority; anything not listed is auto-detected on first
# use (see page_offset.py) and cached to data/page_info_cache.json, so a new book
# needs zero manual entry -- just add it to sources.yaml and ingest it.
PAGE_INFO = {"razavi_analog_cmos": {"offset": 19, "min": 20}}
MAX_BASIC_PAGE = {"razavi_analog_cmos": 470}  # per-book beginner cutoff (page number, estimate); default = no cutoff
_CACHE_FILE = Path("data/page_info_cache.json")


def _load_offset_cache():
    try:
        return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_offset_cache(cache):
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
PDF_PATH = os.environ.get("EE_PDF_PATH", "")
FIG_NUM = re.compile(r"Fig(?:ure)?s?\.?\s*(\d+\.\d+)")
CAP_ANY = re.compile(r"^\s*(?:Figure|Fig\.)\s*\d+\.\d+", re.I)
SMALLTALK = re.compile(
    r"^\s*(hi+|hello+|hey+|yo|thanks?|thank you|ok(ay)?|bye|good (morning|evening)|who are you|what can you do)\W*$",
    re.I,
)
THANKS = re.compile(r"thank|^\s*ok|bye", re.I)
PDF_LOCK = threading.Lock()  # PyMuPDF is not thread-safe


def info(source_id):
    if source_id in PAGE_INFO:
        return PAGE_INFO[source_id]
    cache = _load_offset_cache()
    if source_id in cache:
        return cache[source_id]
    pdf = find_pdf(source_id)
    offset = 0
    if pdf:
        from core.page_offset import detect_offset
        try:
            detected, confidence = detect_offset(pdf)
            if detected is not None and confidence >= 0.4:
                offset = detected
        except Exception:
            pass
    result = {"offset": offset, "min": 1}
    cache[source_id] = result
    _save_offset_cache(cache)
    return result


_STYLE = {
    "beginner": (
        "LEVEL: beginner. Assume a first or second year student. Use very simple words and short "
        "sentences. Define every symbol and term the first time you use it. Prefer a small concrete "
        "example from the sources over abstract statements. Skip heavy derivations."
    ),
    "advanced": (
        "LEVEL: advanced. Assume the student knows basic circuit analysis and digital logic. Be concise "
        "and technical. Skip basics, give the precise statement, conditions and the exact relation."
    ),
}


def build_system(level):
    style = _STYLE.get(level, _STYLE["beginner"])
    return f"""You are EE Tutor: an exceptional, warm, and highly knowledgeable electrical and electronics \
engineering teacher (circuits, analog and digital electronics, computer architecture, signals and systems, \
control, and power). Your role is to explain topics very deeply and in a remarkably efficient manner—giving \
deep physical insight and mathematical clarity in as few words as needed. Your students are university students, \
many preparing for semester exams, GATE, or ESE.

TEACH IN YOUR OWN EE TUTOR VOICE (NEVER COPY-PASTE CHUNKS)
- Synthesize and teach like an expert teacher in your own engaging, clear voice. DO NOT copy-paste raw, stiff sentences \
or verbatim chunks from the sources into the final answer. Digest the concept and explain the intuition, mechanism, and \
why it matters, as a professor speaking directly to a student.
- NO BRACKETED CITATIONS IN TEXT: NEVER output citation numbers or brackets like [1], [2], [4], [p.12] anywhere inside \
your answer, explanation, key points, summary, or reply text. The text must read clean, fluent, and completely free of \
bracketed numbers. Source tracking is handled solely via the "cited" JSON array.

ADAPTIVE PACING (LEARN BY USER'S PACE)
- Continuously observe and adapt to the student's pace, grasp, and tone from the conversation history:
  * Slower / Struggling Pace: If the student asks basic questions, shows hesitation, repeats doubts, or struggles \
with core concepts, slow down. Break explanations into digestible, step-by-step intuition, define every technical \
term, and provide clear intuitive physical analogies before diving into technical details.
  * Fast / Advanced Pace: If the student demonstrates rapid grasp, uses technical terminology, or asks sharp \
analytical/GATE-level questions, accelerate the pace. Provide concise, high-density, mathematically precise \
answers without elementary recaps or unnecessary hand-holding.
  * Dynamically calibrate your explanation depth and pacing to match the student's current learning speed.

SOURCE DISCIPLINE & CONTENT ENRICHMENT (BOOKS AS FOUNDATION + WEB FINE-TUNING)
- Primary Foundation (Textbooks): Follow and prioritize the numbered SOURCES provided in the message as your \
primary ground truth for core definitions, physical mechanisms, equations, and exact notations.
- Fine-Tuning & Adding Reliable Content: You are anchored in the book, but you can also use web search and \
verified engineering knowledge for fine-tuning the answer or adding more reliable, practical, and related content \
(such as real-world industry context, modern intuition, or bridging small gaps not fully elaborated in the excerpt).
- Copy formulas and definitions in standard EE conventions. Never rebuild an equation from memory if the sources provide it.
- If two sources disagree or show conflicting conventions, explain the distinction clearly.
- If the sources cover the main point, answer what they cover, fine-tune/enrich where helpful, and set "found" to true.
- If the sources do not cover the question's main subject at all, set "found" to false. Answer accurately using \
reliable web/engineering knowledge, while noting honestly that this is supplemented beyond their uploaded textbook.

HOW YOU TEACH
- Deep yet ultra-efficient: start with core intuition (what it is, how it physically works, why it matters). \
One idea at a time. No filler, no redundant preamble, no restating the question. Short doubts get short answers.
- Plain words and short sentences. Define jargon when it first appears. Always include units with numbers.
- Analogies: You may add at most one short everyday analogy (beginner level), introduced with "Think of it like", \
strictly to build physical intuition. Never use an analogy to introduce an inaccurate technical claim.
- Encouraging & constructive: If the student makes a misconception: "Good try, here is the catch" and present \
the correct physical insight.
- Student Language: Reply in the student's language. If they write in Hinglish, reply in simple natural Hinglish \
while keeping technical engineering terms in English. No emojis unless the student uses them.
- Exam Relevance: If the student mentions an exam (GATE, ESE, semester), include one sharp "Exam tip:". If the \
topic is broad or visual, end the explanation with: Tip: tap the video icon for an animated walkthrough.

{style}

TWO REPLY SHAPES
1. New topic question, mode "card":
   - answer: the direct answer in 1 or 2 sentences in your own clear words, without any bracketed citation numbers.
   - explanation: 3 to 5 short sentences in logical order, explaining deeply and clearly. The LAST sentence is \
the conclusion, starting with "In short,". Do not write bracketed numbers.
   - key_points: 3 to 5 things to remember, each under 15 words. If applicable, start one with "Watch out:".
   - formula: the single most important equation from the sources/standard EE notation, or "".
   - formula_where: one line defining the symbols, from the sources, or "".
   - mindmap: (optional) {{"center": "topic, max 4 words", "branches": [{{"label": "max 4 words", "children": ["max 6 words"]}}]}} \
with 3 to 5 branches, or null if not applicable.
   - flowchart: (optional) Mermaid structure {{"direction": "TD", "nodes": [{{"id": "A", "label": "max 6 words", "shape": "box"}}], "edges": [{{"from": "A", "to": "B", "label": "max 3 words"}}]}} \
if describing a process or signal flow, else null.
   - steps: 3 to 6 short ordered strings if describing a procedure, else [].
   - example: one short worked example or analogy if helpful, else "".
   - summary: 2 to 4 bullet strings recapping key takeaways, or [].
   - followups: 3 short, thought-provoking follow-up questions to test or expand understanding.
2. Follow-up, clarification, doubt or challenge (MUST use mode "chat"):
   - mode: "chat"
   - reply: 2 to 6 sentences, direct, engaging, and specifically answering the new question.
   - ZERO REPETITION: NEVER repeat high-level definitions, overviews, or sentences already given earlier in the conversation.
   - DIVE INTO THE MECHANISM: Explain the underlying physical cause-and-effect (e.g. at the clock cycle, register, or circuit level) instead of staying at the surface.
   - ADAPT TO USER PACE:
     * If the user asks for intuition, says "why", "how does that work", or seems confused: SLOW DOWN. Drop textbook jargon, give a simple real-world analogy or visual mental model, and walk through it step-by-step.
     * If the user asks a fast, sharp technical question: ACCELERATE. Give the exact engineering trade-off or analytical principle without unnecessary preliminaries.
   - If the student challenges an earlier statement, re-check against the sources. If they are right, acknowledge and correct it honestly.
   - If the student repeats a doubt, explain from a completely fresh angle with a brand new analogy.

Return ONLY a JSON object (no markdown fences) with these keys:
"mode": "card" for a new topic, "chat" for a follow-up, doubt or challenge
"title": (card) short topic name, max 8 words
"answer": (card) the direct answer, 1 or 2 sentences
"explanation": (card) 3 to 5 sentences, ending with the "In short," conclusion
"key_points": (card) list of 3 to 5 short strings
"formula": (card) key equation as plain ASCII text copied from the sources, or ""
"formula_where": (card) one line defining symbols, from the sources, or ""
"mindmap": (card) mind map object or null
"flowchart": (card) flowchart object or null
"steps": (card) procedure steps list or []
"example": (card) worked example or analogy string, or ""
"summary": (card) recap bullets list or []
"followups": (card and chat) 3 follow-up questions list or []
"reply": (chat) 2 to 6 sentences, direct and natural, with no bracketed numbers
"figures": up to 2 figure numbers chosen ONLY from candidate list that best illustrate the answer, or []
"cited": list of the source numbers that support what you wrote (e.g. [1, 2])
"found": true if the sources answer the main question, false if they do not cover it
Never invent facts, formulas, figure numbers, page numbers or source numbers."""


WEB_SYSTEM = """You are answering a question that the student's textbook sources do NOT cover.
You are given short snippets from a web search instead. This is a fallback path, separate from the
book-grounded mode -- here you may use the web snippets and well-established general engineering
knowledge to give a genuinely useful answer, but:
1. Stay factual and cautious; do not present uncertain or unverified claims as settled fact.
2. Keep it concise: 3-6 sentences, at the level implied by the student's message.
3. Cite the web sources you actually relied on, inline like [W1], [W2].
Return ONLY a JSON object (no markdown fences):
"reply": the answer, 3-6 sentences, with inline [W#] citations
"used": list of the web source numbers you actually relied on
If even the web snippets do not answer the question, set "reply" to a short honest statement that you
don't have a good answer, and "used" to []."""

GENERAL_SYSTEM = (
    "You are a friendly tutor. The student asked something outside their textbook and web search "
    "is unavailable, so answer from well-established general knowledge in 3-6 plain sentences. "
    "If you are not sure, say so instead of guessing."
)

REWRITE_SYSTEM = (
    "The student is asking a follow-up question in an ongoing tutoring chat. "
    "Rewrite their last message into a focused search query for an electrical engineering textbook, "
    "specifically targeting the NEW specific sub-mechanism, concept, or doubt they are inquiring about "
    "(avoid broad introductory terms already discussed). Return only the query, max 15 words."
)


def parse_json(text):
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def strip_citations(text):
    if not text:
        return ""
    # Strip any bracketed citations like [1], [1, 2], [p.12], [W1], [W2] and clean whitespace
    text = re.sub(r"\s*\[(?:\s*p\.?\s*\d+|\d+(?:\s*,\s*\d+)*|W\d+)\s*\]", "", str(text))
    return re.sub(r" +", " ", text).strip()


STOPWORDS = set("""a an the is are was were be been being of to in on for and or as at by with from into
this that these those it its it's their his her they he she you your we our not no can may might will
would should could than then so such also which what when where how why do does did have has had""".split())


def content_words(text):
    return {w for w in re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower()) if w not in STOPWORDS}


def grounding_score(answer_text, cited_sources):
    """Cheap lexical-overlap check: what fraction of the answer's content words also
    appear somewhere in the cited source passages. Not a semantic check, just a safety
    net to flag answers that read like generic/outside-knowledge text rather than
    something pulled from this book. Low score -> show a caution banner, don't hide it."""
    words = content_words(answer_text)
    if not words:
        return 1.0
    corpus = content_words(" ".join(s["text"] for s in cited_sources))
    if not corpus:
        return 0.0
    return round(len(words & corpus) / len(words), 2)


@lru_cache(maxsize=1)
def get_retriever():
    return Retriever()


def retrieve(query, level):
    hits = get_retriever().search(query, k=20, mode="rerank")
    hits = [(c, s) for c, s in hits if c["page"] >= info(c["source_id"])["min"]]
    if level == "beginner":
        hits = [(c, s) for c, s in hits if c["page"] <= MAX_BASIC_PAGE.get(c["source_id"], 10**6)]
    hits = hits[:5]
    return [
        {
            "n": i,
            "source": c["source_id"],
            "page": c["page"] - info(c["source_id"])["offset"],
            "pdf_page": c["page"],
            "text": c["text"],
            "score": None if s is None else float(s),
        }
        for i, (c, s) in enumerate(hits, 1)
    ]


def history_text(msgs, n=6):
    out = []
    for m in msgs[-n:]:
        if m["role"] == "user":
            out.append("Student: " + m["content"])
        else:
            r = m.get("res", {})
            body = r.get("reply") or (r.get("answer", "") + " " + r.get("explanation", ""))
            out.append("Tutor: " + body.strip()[:700])
    return "\n".join(out)


def standalone_query(q, hist, prev_q):
    try:
        out = generate(REWRITE_SYSTEM, f"Conversation:\n{hist}\n\nLast student message: {q}")
        return out.strip().strip('"').splitlines()[0][:200] or q
    except Exception:
        return f"{prev_q} {q}".strip()


def fig_page(sources, no):
    for s in sources:
        if re.search(rf"Fig(?:ure)?s?\.?\s*{re.escape(no)}(?!\d)", s["text"]):
            return s["pdf_page"]
    return sources[0]["pdf_page"]


def web_fallback(query):
    """For questions outside the textbook. Tries, in order: (1) Gemini + Google Search,
    (2) Tavily snippets if TAVILY_API_KEY is set, (3) plain general knowledge."""
    g = grounded_answer(query)
    if g:
        return {"web_used": True, "web_sources": g["sources"], "reply": strip_citations(g["reply"])}

    results = web_search(query)
    if results:
        snippets = "\n\n".join(f"[W{i}] {r['title']}\n{r['snippet']}" for i, r in enumerate(results, 1))
        user = f"Question: {query}\n\nWeb search snippets:\n{snippets}"
        try:
            d = parse_json(generate(WEB_SYSTEM, user))
            used = [i for i in d.get("used", []) if isinstance(i, int) and 1 <= i <= len(results)]
            reply = str(d.get("reply", "")).strip()
            if reply:
                return {"web_used": True, "web_sources": [results[i - 1] for i in used] or results[:2], "reply": strip_citations(reply)}
        except Exception:
            pass

    try:  # last resort: no web available, answer from general knowledge and say so
        txt = generate(GENERAL_SYSTEM, query).strip()
    except Exception:
        return None
    if not txt:
        return None
    return {"web_used": False, "web_sources": [],
            "reply": "This isn't in your textbook, and web search wasn't available, so this is general knowledge:\n\n" + txt}

def respond(msgs, level):
    q = msgs[-1]["content"]
    prior = msgs[:-1]
    first = not prior
    base = {"mode": "chat", "found": False, "reply": "", "answer": "", "explanation": "", "title": "",
            "key_points": [], "formula": "", "formula_where": "", "figures": [], "figure_pages": {},
            "sources": [], "cited": [], "search_q": q, "web_used": False, "web_sources": []}

    if SMALLTALK.match(q):  # greetings never go to retrieval
        if THANKS.search(q):
            return dict(base, reply="You're welcome! Ask another doubt whenever you like.")
        return dict(base, reply="Hi! I'm your EE tutor. Ask me anything from your textbook, "
                                "for example: why does drain current stop increasing at large Vds?")

    hist = history_text(prior)
    prev_q = next((m["content"] for m in reversed(prior) if m["role"] == "user"), "")
    search_q = q if first else standalone_query(q, hist, prev_q)
    sources = retrieve(search_q, level)
    base.update(sources=sources, search_q=search_q)
    if not sources:
        fb = web_fallback(search_q)
        if fb:
            return dict(base, mode="chat", found=False, **fb)
        return dict(base, reply="I could not find anything relevant in the book for that, "
                                "and I could not reach the web either. Try rephrasing.")
    if not llm_ready():
        return dict(base, found=True, cited=[1],
                    reply="No LLM is configured. Best matching passage: " + sources[0]["text"][:600])

    cands = list(dict.fromkeys(n for s in sources for n in FIG_NUM.findall(s["text"])))
    context = "\n\n".join(f"[{s['n']}] {s['text']}" for s in sources)
    user = (
        f"Earlier conversation:\n{hist or '(none)'}\n\n"
        f"Sources:\n{context}\n\n"
        f"Candidate figures mentioned in the sources: {', '.join(cands) or 'none'}\n\n"
        f"Student's message: {q}\n"
        + (
            "This is the first message about a topic, so mode must be 'card'.\n"
            if first
            else "This is a FOLLOW-UP question in an ongoing conversation. Mode MUST be 'chat'.\n"
                 "RULES FOR THIS FOLLOW-UP:\n"
                 "1. Do NOT repeat definitions or overviews already given in Earlier conversation.\n"
                 "2. Directly answer the student's specific doubt or 'how/why' question from the first sentence.\n"
                 "3. Calibrate your pace: if the user asks 'how/why' or seems confused, slow down and explain the inner physical/hardware mechanism simply; if advanced, be concise and technical.\n"
                 "4. If the source snippets are surface-level, use verified engineering knowledge to explain the actual mechanism thoroughly rather than repeating the same snippet.\n"
        )
    )
    raw = generate(build_system(level), user)
    try:
        d = parse_json(raw)
    except Exception:
        return dict(base, found=True, cited=[1], reply=raw[:1200])

    found = bool(d.get("found", True))
    mode = "card" if first else "chat"
    reply = strip_citations(str(d.get("reply", "")))
    if not reply and mode == "chat":  # model filled card fields instead of reply
        reply = (str(d.get("answer", "")) + " " + str(d.get("explanation", ""))).strip()
    if mode == "card" and found and not (d.get("answer") or d.get("explanation")):
        mode, reply = "chat", reply or "I could not form a clear answer from the sources. Try rephrasing."
    if not reply and mode == "chat":
        reply = "I could not form a clear answer from the sources. Try rephrasing your question."
    cited = [n for n in d.get("cited", []) if isinstance(n, int) and 1 <= n <= len(sources)]
    figs = [str(f) for f in d.get("figures", []) if str(f) in cands][:2] if found else []
    cited_list = list(dict.fromkeys(cited)) or ([1] if found else [])
    cited_sources = [s for s in sources if s["n"] in cited_list] or sources[:1]
    answer_text = " ".join([
        str(d.get("answer", "")), str(d.get("explanation", "")),
        " ".join(str(x) for x in d.get("key_points", [])), reply,
    ])
    score = grounding_score(answer_text, cited_sources) if found else 1.0
    LOW_GROUNDING = 0.35  # heuristic threshold; tune once you have labeled examples

    reply = strip_citations(reply)
    answer = strip_citations(d.get("answer", ""))
    explanation = strip_citations(d.get("explanation", ""))
    title = strip_citations(d.get("title", ""))
    key_points = [strip_citations(x) for x in d.get("key_points", []) if strip_citations(x)][:6]
    formula_where = strip_citations(d.get("formula_where", ""))

    result = dict(
        base, mode=mode, found=found,
        title=title,
        answer=answer,
        explanation=explanation,
        key_points=key_points,
        formula=str(d.get("formula", "")),
        formula_where=formula_where,
        reply=reply,
        figures=figs,
        figure_pages={f: fig_page(sources, f) for f in figs},
        cited=cited_list,
        grounding_score=score,
        low_grounding=bool(found and score < LOW_GROUNDING),
    )

    result.update(clean_extras(d))
    if not found:
        fb = web_fallback(search_q)
        if fb:
            result.update(mode="chat", **fb)
            result["cited"], result["figures"] = [], []
            result.update(mindmap=None, steps=[], example="", summary=[], followups=[])  # a web answer cites web sources, not book pages
        elif not result["reply"]:
            result["reply"] = "This isn't covered in your sources, and I couldn't reach the web either."
    return result


# ---------- book figures ----------
def find_pdf(source_id):
    if PDF_PATH and Path(PDF_PATH).exists():
        return PDF_PATH
    pdfs = list(Path("data").rglob("*.pdf"))
    key = source_id.lower().split("_")[0]
    for p in pdfs:
        if key in p.name.lower():
            return str(p)
    return str(pdfs[0]) if len(pdfs) == 1 else None


def graphic_rects(page):
    pr = page.rect
    rects = []
    try:
        rects += [pymupdf.Rect(r) for r in page.cluster_drawings()]
    except Exception:
        pass
    try:
        rects += [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
    except Exception:
        pass
    return [r for r in rects
            if not (r.is_empty or r.width < 15 or r.height < 8 or r.y1 < 50)
            and r.width * r.height <= 0.8 * pr.width * pr.height]


@lru_cache(maxsize=128)
def crop_figure(pdf_path, fig_no, near, offset):
    with PDF_LOCK:
        doc = pymupdf.open(pdf_path)
        try:
            pat = re.compile(rf"^\s*(?:Figure|Fig\.)\s*{re.escape(fig_no)}(?!\d)", re.I)
            for p in (near, near + 1, near - 1, near + 2):
                if p < 1 or p > len(doc):
                    continue
                page = doc[p - 1]
                blocks = [b for b in page.get_text("blocks") if b[6] == 0]
                caps = [b for b in blocks if pat.match(b[4]) and len(b[4].split()) <= 70]
                if not caps:
                    continue
                gr = graphic_rects(page)
                for cap in caps:
                    capr = pymupdf.Rect(cap[:4])
                    top = 40.0
                    for b in blocks:
                        if b[3] <= capr.y0 - 1 and (len(b[4].split()) >= 25 or CAP_ANY.match(b[4])):
                            top = max(top, b[3])
                    g = [r for r in gr if r.y1 <= capr.y0 + 6 and r.y0 >= top - 4]
                    if not g:
                        continue
                    u = pymupdf.Rect(g[0])
                    for r in g[1:]:
                        u.include_rect(r)
                    zone = pymupdf.Rect(u.x0 - 30, max(top, u.y0 - 20), u.x1 + 30, capr.y0)
                    for b in blocks:
                        r = pymupdf.Rect(b[:4])
                        if (len(b[4].split()) <= 10 and r.intersects(zone) and r.y0 >= top
                                and r.y1 <= capr.y0 and not CAP_ANY.match(b[4])):
                            u.include_rect(r)
                    u.include_rect(capr)
                    clip = pymupdf.Rect(u.x0 - 10, max(top, u.y0 - 8), u.x1 + 10, u.y1 + 4)
                    clip.intersect(page.rect)
                    if clip.height < 40 or clip.width < 40:
                        continue
                    return {"png": page.get_pixmap(clip=clip, dpi=170).tobytes("png"), "printed": p - offset}
            return None
        finally:
            doc.close()


@lru_cache(maxsize=32)
def page_image(pdf_path, pdf_page):
    with PDF_LOCK:
        doc = pymupdf.open(pdf_path)
        try:
            return doc[pdf_page - 1].get_pixmap(dpi=110).tobytes("png")
        finally:
            doc.close()


def generate_video_plan(query, level):
    """RAG + the same grounding discipline as respond(), but asks for a scene-by-scene
    video script instead of a text answer. Returns a dict with found/video_title/scenes,
    or reason set when found is False."""
    sources = retrieve(query, level)
    if not sources:
        return {"found": False, "video_title": "", "scenes": [],
                "reason": "Nothing relevant was found in your sources for this topic."}
    if not llm_ready():
        return {"found": False, "video_title": "", "scenes": [], "reason": "No LLM is configured."}

    context = "\n\n".join(f"[{s['n']}] {s['text']}" for s in sources)
    user = f"Sources:\n{context}\n\nTopic requested: {query}"
    try:
        raw = generate(build_video_prompt(query), user)
        d = parse_json(raw)
    except Exception as e:
        return {"found": False, "video_title": "", "scenes": [], "reason": f"Could not plan the video ({e})."}

    if not d.get("found", True) or not d.get("scenes"):
        return {"found": False, "video_title": d.get("video_title", ""), "scenes": [],
                "reason": d.get("reason", "The sources don't cover this topic well enough for a video.")}

    scenes = d["scenes"]
    for sc in scenes:
        # citations in the video reference book pages the same way text answers do
        sc["citation"] = str(sc.get("citation", ""))
    if estimate_seconds(scenes) > MAX_SECONDS:
        scenes = trim_to_budget(scenes)
    scenes = sanitize_scenes(scenes)
    return {"found": True, "video_title": str(d.get("video_title", query))[:80], "scenes": scenes}


VIDEO_DIR = Path("data/videos")
_video_jobs = {}  # job_id -> {"status": "planning"|"rendering"|"done"|"error", "title": str, "seconds": float, "error": str}


_nptel_by_job = {}  # job_id -> matching NPTEL clip (or None)


def _nptel_clip(text):
    """Best NPTEL lecture clip for this text, or None (also None if no lectures were added yet)."""
    try:
        from core.nptel.search import find_clip
        return find_clip(text)
    except Exception as e:
        print("NPTEL lookup skipped:", e)
        return None


def start_video_job(job_id, query, level):
    _video_jobs[job_id] = {"status": "planning", "title": "", "seconds": 0, "error": ""}
    _nptel_by_job[job_id] = _nptel_clip(query)  # instant, shown while the animation is still being made
    try:
        plan = generate_video_plan(query, level)
        if not plan["found"]:
            _video_jobs[job_id] = {"status": "error", "title": plan.get("video_title", ""),
                                    "seconds": 0, "error": plan.get("reason", "Not covered by your sources.")}
            return
        _video_jobs[job_id]["status"] = "rendering"
        _video_jobs[job_id]["title"] = plan["video_title"]
        richer = " ".join([query, plan["video_title"]] + [s.get("title", "") for s in plan["scenes"]])
        _nptel_by_job[job_id] = _nptel_clip(richer) or _nptel_by_job.get(job_id)  # sharper match from the plan
        VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        work = VIDEO_DIR / job_id
        work.mkdir(parents=True, exist_ok=True)
        (work / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        with open(work / "worker.log", "w", encoding="utf-8") as log:  # rendering runs in its own process
            proc = subprocess.Popen([sys.executable, "-m", "core.video.worker", job_id], stdout=log, stderr=subprocess.STDOUT)
            try:
                proc.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise RuntimeError("rendering took longer than 30 minutes and was stopped")
        if proc.returncode != 0 or not (VIDEO_DIR / f"{job_id}.mp4").exists():
            tail = (work / "worker.log").read_text(encoding="utf-8", errors="replace")[-700:]
            raise RuntimeError(tail.strip() or "the render process crashed")
        total_seconds = json.loads((work / "result.json").read_text(encoding="utf-8"))["seconds"]
        _video_jobs[job_id] = {"status": "done", "title": plan["video_title"],
                                "seconds": round(total_seconds, 1), "error": ""}
        try:  # remember title/length so the video still shows up after a server restart
            (VIDEO_DIR / f"{job_id}.json").write_text(
                json.dumps({"title": plan["video_title"], "seconds": round(total_seconds, 1), "nptel": _nptel_by_job.get(job_id)}), encoding="utf-8")
        except Exception:
            pass
    except Exception as e:
        _video_jobs[job_id] = {"status": "error", "title": _video_jobs.get(job_id, {}).get("title", ""),
                                "seconds": 0, "error": f"Video generation failed: {e}"}


def get_video_job(job_id):
    job = _video_jobs.get(job_id)
    if job is None and (VIDEO_DIR / f"{job_id}.mp4").exists():  # finished earlier, server restarted since
        meta = {}
        try:
            meta = json.loads((VIDEO_DIR / f"{job_id}.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        job = {"status": "done", "title": meta.get("title", ""), "seconds": meta.get("seconds", 0), "error": ""}
        _nptel_by_job.setdefault(job_id, meta.get("nptel"))
    if job is None:
        return None
    job = {**job, "nptel": _nptel_by_job.get(job_id)}
    if job.get("status") == "rendering":  # live progress written by the render process
        try:
            job.update(json.loads((VIDEO_DIR / job_id / "progress.json").read_text(encoding="utf-8")))
        except Exception:
            pass
    return job
