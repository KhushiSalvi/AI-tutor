"""Rich text output enrichment step (mindmap, highlights, callouts).
Runs after verification on the final verified answer text only.
LLM cannot add new facts; backend sanitizes and validates all outputs.
"""
import json
import re
from core.llm import generate, parse_json

VALID_HIGHLIGHT_KINDS = {"term", "formula", "warning", "exam"}
VALID_CALLOUT_KINDS = {"important", "remember", "watch_out", "exam_tip"}

ENRICH_SYSTEM = """You are an educational structuring assistant.
Given a verified explanation text, extract visual learning aids.
DO NOT introduce any new facts, claims, or formulas not present in the text.

Return ONLY a JSON object with this exact structure:
{
  "mindmap": {
    "label": "Root Topic (max 4 words)",
    "children": [
      {
        "label": "Subtopic (max 4 words)",
        "children": [
          {"label": "Detail (max 4 words)", "children": []}
        ]
      }
    ]
  },
  "highlights": [
    {"text": "exact substring from the text", "kind": "term|formula|warning|exam"}
  ],
  "callouts": [
    {"kind": "important|remember|watch_out|exam_tip", "title": "short heading", "text": "key takeaway directly from the text"}
  ]
}

Constraints:
1. Every item in 'highlights' MUST BE an EXACT case-sensitive substring of the text.
2. The mindmap must have at most 3 levels of depth and at most 12 nodes in total. Each label must be at most 4 words.
3. Callouts must contain 1 to 4 items."""


def count_sentences(text: str) -> int:
    if not text:
        return 0
    # Match sentences ending with punctuation
    s = [x.strip() for x in re.split(r"[.!?]+(?:\s+|$)", text.strip()) if x.strip()]
    return len(s)


def sanitize_mindmap(node: dict | None, current_depth: int = 1, counter: list[int] | None = None) -> dict | None:
    """Validates and enforces: max depth 3, max 12 nodes, max 4 words per label."""
    if not node or not isinstance(node, dict):
        return None
    if counter is None:
        counter = [0]

    if counter[0] >= 12 or current_depth > 3:
        return None

    raw_label = str(node.get("label", "")).strip()
    if not raw_label:
        return None

    words = raw_label.split()
    label = " ".join(words[:4])  # Max 4 words
    counter[0] += 1

    sanitized_children = []
    if current_depth < 3:
        for child in node.get("children", []) or []:
            if counter[0] >= 12:
                break
            clean_child = sanitize_mindmap(child, current_depth + 1, counter)
            if clean_child:
                sanitized_children.append(clean_child)

    return {"label": label, "children": sanitized_children}


def sanitize_highlights(highlights: list | None, full_text: str) -> list[dict]:
    """Drops any highlight that is not an EXACT substring of full_text."""
    if not highlights or not isinstance(highlights, list) or not full_text:
        return []

    clean = []
    seen = set()
    for h in highlights:
        if not isinstance(h, dict):
            continue
        text = str(h.get("text", "")).strip()
        kind = str(h.get("kind", "")).lower().strip()
        if not text or len(text) < 2:
            continue
        if kind not in VALID_HIGHLIGHT_KINDS:
            kind = "term"

        # Hard Rule: Each text must be an exact substring of the answer; backend drops any that is not
        if text in full_text and (text, kind) not in seen:
            seen.add((text, kind))
            clean.append({"text": text, "kind": kind})

    # Sort by descending length so frontend can highlight longer phrases before substrings
    clean.sort(key=lambda x: len(x["text"]), reverse=True)
    return clean[:15]


def sanitize_callouts(callouts: list | None) -> list[dict]:
    """Ensures 1 to 4 valid callouts with valid kinds."""
    if not callouts or not isinstance(callouts, list):
        return []

    clean = []
    for c in callouts:
        if not isinstance(c, dict):
            continue
        kind = str(c.get("kind", "")).lower().strip()
        if kind not in VALID_CALLOUT_KINDS:
            kind = "important"
        text = str(c.get("text", "")).strip()
        title = str(c.get("title", "")).strip()
        if not text:
            continue
        clean.append({"kind": kind, "title": title or kind.replace("_", " ").title(), "text": text})

    return clean[:4]


def enrich_answer(answer_text: str, client_override=None) -> dict | None:
    """Enriches verified answer text with mindmap, highlights, and callouts.
    Short chat replies (<= 3 sentences) skip enrichment."""
    if count_sentences(answer_text) <= 3:
        return None

    try:
        user_prompt = f"Answer text to enrich:\n\n{answer_text}"
        raw = generate(ENRICH_SYSTEM, user_prompt)
        d = parse_json(raw)
        if not isinstance(d, dict):
            return None

        mm = sanitize_mindmap(d.get("mindmap"))
        hl = sanitize_highlights(d.get("highlights"), answer_text)
        co = sanitize_callouts(d.get("callouts"))

        if not mm and not hl and not co:
            return None

        return {
            "mindmap": mm,
            "highlights": hl,
            "callouts": co,
        }
    except Exception as e:
        print(f"Enrichment skipped or failed: {e}")
        return None
