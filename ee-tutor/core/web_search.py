"""Web-search fallback for questions the book sources don't cover.

Used ONLY when the book-grounded pass says found=False. Kept in its own module and
its own prompt so the strict "book only" rules in build_system() are never touched --
this is a clearly separate, clearly labeled path.

Two web sources, tried in this order by tutor.web_fallback():
  1. grounded_answer(): Gemini with Google Search switched on. Uses the SAME Gemini key
     you already have, so no extra signup is needed.
  2. web_search(): Tavily snippets, only if TAVILY_API_KEY is set (free tier: tavily.com).
Both return nothing (never crash) on network/quota errors.
"""
import os

import requests

TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

GROUNDED_SYSTEM = (
    "You are a friendly tutor for an engineering student. The question is outside the student's "
    "textbook, so answer it using web search results. Be accurate and concise (3-6 sentences), "
    "plain language, no markdown headings. If the web results do not give a reliable answer, "
    "say so honestly instead of guessing."
)


def grounded_answer(query, timeout=30):
    """Ask Gemini with Google Search grounding. Returns {"reply", "sources"} or None."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if not key:
        return None
    try:
        r = requests.post(
            GEMINI_URL.format(model=model.replace("models/", "")),
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": GROUNDED_SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": query}]}],
                "tools": [{"google_search": {}}],
            },
            timeout=timeout,
        )
        r.raise_for_status()
        cand = r.json()["candidates"][0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])).strip()
        if not text:
            return None
        sources, seen = [], set()
        for c in cand.get("groundingMetadata", {}).get("groundingChunks", []):
            w = c.get("web") or {}
            url = w.get("uri")
            if url and url not in seen:
                seen.add(url)
                sources.append({"title": (w.get("title") or url)[:120], "url": url, "snippet": ""})
                return {"reply": text, "sources": sources[:4]}
    except Exception as e:
        resp = getattr(e, "response", None)
        print("[web] Google Search call failed:", repr(e)[:200], (resp.text[:300] if resp is not None else ""), flush=True)
        return None
TAVILY_URL = "https://api.tavily.com/search"


def web_search(query, k=4):
    if not TAVILY_KEY:
        return []
    try:
        r = requests.post(
            TAVILY_URL,
            json={
                "api_key": TAVILY_KEY,
                "query": f"{query} electrical engineering",
                "max_results": k,
                "search_depth": "basic",
            },
            timeout=8,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        return [
            {"title": x.get("title", "")[:120], "url": x.get("url", ""), "snippet": (x.get("content") or "")[:600]}
            for x in results
            if x.get("url")
        ][:k]
    except Exception:
        return []  # network/quota errors degrade to "not covered", never crash the chat