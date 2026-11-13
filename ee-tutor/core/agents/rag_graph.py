"""Explicit LangGraph Agent State Graph for EE Tutor RAG and Video Planning.
Implements:
- Understand (intent, context rewriting, compound splitting)
- Retrieve & Deduplicate
- Grade & Retry (max 2 retries)
- Coverage Check (COVERED, PARTIAL, NOT_COVERED with mode-specific disambiguation)
- Route Text & Route Video
- Verify (entailment checking against book chunks)
- Enrich (rich visual aids from verified text: mindmap, highlights, callouts)
- Learner Memory Profile
- Trace logging to data/traces.jsonl
"""
import json
import os
import re
import time
from pathlib import Path
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

from core.llm import generate, parse_json, llm_ready
from core.retrieval.coverage import check_coverage
from core.video.web_videos import find_web_videos
from core.enrich import enrich_answer
from core.web_search import web_search, grounded_answer
from core.answer_extras import clean_extras

TRACES_FILE = Path("data/traces.jsonl")
LEARNER_PROFILE_FILE = Path("data/learner_profile.json")
MAX_NODE_VISITS = 12

INTENT_SYSTEM = """You are a query understanding assistant for an EE/CS tutor.

Given the conversation history and the student's latest message:
1. Classify intent as ONE of:
   - smalltalk: greetings, thanks, goodbyes, casual chitchat
   - new_topic_explain: asking to explain, introduce, or teach a new concept
   - specific_doubt: focused technical question about a specific detail
   - follow_up: continuing or drilling deeper into the PREVIOUS topic
   - challenge: tricky counter-example, edge-case, or debate question
   - exam_question: numerical, derivation, or exam-style problem
   - out_of_scope: non-technical or entirely non-EE/CS

2. Rewrite the student's message into 1-3 FULLY STANDALONE search queries.
   - For follow_up or specific_doubt: ALWAYS include the topic from prior context.
     Example: if prior topic was "MOSFET" and student says "what about the body effect?",
     write "MOSFET body effect threshold voltage".
   - Never write a query that only makes sense with prior context (e.g., "what about that?").
   - If compound, split into separate queries.

Return ONLY a JSON object:
{
  "intent": "...",
  "queries": ["standalone query 1", "standalone query 2"]
}"""

BOOK_ANSWER_SYSTEM = """You are EE Tutor: an exceptional, warm, and highly knowledgeable electrical and electronics \
engineering teacher. Ground all factual assertions STRICTLY in the provided textbook passages.

CONVERSATION AWARENESS
- You are given the last few turns of the conversation. Use them to:
  * Avoid repeating what was already explained.
  * Build on what the student already knows from this conversation.
  * Answer follow-up questions precisely — go deeper, not broader.
  * If the student said "explain more" or "why?" — expand on the SPECIFIC point they're confused about.
- Never restart from scratch if the topic was already introduced. Continue from where you left off.

READABILITY, STRUCTURE & BREATHING ROOM
- Short Paragraphs: strictly 2-3 sentences each, separated by double newlines (\\n\\n).
- Key Terms in Bold: Use **bold** on the first mention of critical variables, parameters, or components.
- NO BRACKETED CITATIONS IN TEXT: NEVER write [1], [2], [p.12] in the text. Cite only via the "cited" integer array.

Return ONLY a JSON object:
{
  "mode": "card" | "chat",
  "title": "Topic name (max 8 words)",
  "answer": "1-2 sentence core conceptual summary",
  "explanation": "2-3 short, well-spaced paragraphs",
  "key_points": ["bullet 1", "bullet 2", "bullet 3"],
  "formula": "Governing equation or ''",
  "formula_where": "Variable definitions or ''",
  "cited": [1, 2]
}"""

PARTIAL_ANSWER_SYSTEM = """You are EE Tutor. The student asked a question that is only PARTIALLY covered in our engineering textbooks.
Answer the part that IS covered in the sources first, grounded strictly in the book sources.
Do NOT fabricate book citations for the rest.

Return ONLY a JSON object:
{
  "mode": "card",
  "title": "Topic name (max 8 words)",
  "answer": "Core summary of the covered portion",
  "explanation": "Detailed explanation of the covered portion",
  "key_points": ["bullet 1", "bullet 2"],
  "formula": "formula or ''",
  "formula_where": "explanation or ''",
  "cited": [1]
}"""

WEB_ANSWER_SYSTEM = """You are EE Tutor. This topic is NOT in the student's curriculum textbooks.
Answer clearly based ONLY on the provided live web search snippets.
Use inline citations like [W1], [W2] referencing the snippet numbers.

Return ONLY a JSON object:
{
  "mode": "card",
  "title": "Topic name (max 8 words)",
  "answer": "Clear direct answer from web search",
  "explanation": "Structured explanation citing [W1], [W2]",
  "key_points": ["key takeaway 1", "key takeaway 2"],
  "formula": "",
  "formula_where": ""
}"""


class TutorState(TypedDict):
    messages: list[dict]
    query: str
    level: str
    mode: str  # "text" or "video"
    intent: str
    sub_queries: list[str]
    retry_count: int
    sources: list[dict]
    coverage: str  # "COVERED", "PARTIAL", "NOT_COVERED"
    coverage_meta: dict
    answer_text: str
    structured_data: dict
    web_sources: list[dict]
    web_videos: list[dict]
    verification: dict
    enrichment: dict | None
    final_result: dict
    node_visits: int
    trace: list[str]


def log_trace(state: TutorState):
    TRACES_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "query": state.get("query"),
        "mode": state.get("mode"),
        "intent": state.get("intent"),
        "coverage": state.get("coverage"),
        "sub_queries": state.get("sub_queries"),
        "sources_count": len(state.get("sources", [])),
        "node_visits": state.get("node_visits", 0),
        "trace": state.get("trace", []),
    }
    try:
        with open(TRACES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def update_learner_profile(query: str, topic: str, level: str):
    LEARNER_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    profile = {"level": level, "topics_asked": [], "last_active": time.time()}
    try:
        if LEARNER_PROFILE_FILE.exists():
            profile = json.loads(LEARNER_PROFILE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

    topics = profile.get("topics_asked", [])
    if topic and topic not in topics:
        topics.append(topic)
    profile["topics_asked"] = topics[-50:]
    profile["last_active"] = time.time()
    profile["level"] = level
    try:
        LEARNER_PROFILE_FILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ------------------ NODES ------------------

def understand_node(state: TutorState) -> dict:
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["understand"]
    q = state["query"]
    prior = state.get("messages", [])[:-1]

    # Greeting / thanks check
    if re.match(r"^\s*(hi+|hello+|hey+|yo)(\s+(there|buddy|everyone|all))?\W*$", q, re.I) or re.match(r"^\s*good\s+(morning|evening|afternoon)\W*$", q, re.I):
        return {
            "intent": "smalltalk",
            "sub_queries": [q],
            "node_visits": visits,
            "trace": trace,
            "final_result": {
                "mode": "chat",
                "found": False,
                "reply": "Hi! I'm your EE tutor. Ask me anything from your textbook, for example: how does a MOSFET saturate?",
                "sources": [],
                "source_kind": "system",
            }
        }

    if re.search(r"^\s*(thanks?|thank you|ok(ay)?|bye)\W*$", q, re.I):
        return {
            "intent": "smalltalk",
            "sub_queries": [q],
            "node_visits": visits,
            "trace": trace,
            "final_result": {
                "mode": "chat",
                "found": False,
                "reply": "You're welcome! Feel free to ask whenever you have another doubt.",
                "sources": [],
                "source_kind": "system",
            }
        }

    # Context query rewrite — build a richer conversation string
    context_str = ""
    prior_topic = ""
    if prior:
        hist_parts = []
        for m in prior[-6:]:   # last 6 turns (3 exchanges)
            role = "Student" if m["role"] == "user" else "Tutor"
            if m["role"] == "user":
                content = m.get("content", "")[:400]
            else:
                res_obj = m.get("res") or {}
                content = (
                    res_obj.get("answer", "") or
                    res_obj.get("reply", "") or
                    str(res_obj)[:200]
                )[:600]
                # Extract the topic from the last tutor answer for fast-path follow-up
                if not prior_topic:
                    prior_topic = (m.get("res") or {}).get("title", "")
            if content.strip():
                hist_parts.append(f"{role}: {content}")
        context_str = "\n".join(hist_parts)

    # --- FAST PATH: skip LLM understand call for obvious follow-ups ---
    # Heuristic: short query + we have prior context = very likely a follow-up
    _FOLLOWUP_PATTERNS = re.compile(
        r"^(why|how|what|when|where|can you|could you|explain|tell me|give|more|"
        r"elaborate|example|and|but|so|then|also|is it|does it|are|do|did|"
        r"what about|what if|how about|huh|really|seriously|ok so|okay so|"
        r"i mean|i see|i don.t|i don't|help|please|any|another|again|"
        r"what's|whats|why does|why is|how does|how is|can|show)\b",
        re.I,
    )
    is_short = len(q.split()) <= 12
    has_context = bool(prior_topic or context_str)

    if has_context and is_short and _FOLLOWUP_PATTERNS.match(q.strip()):
        # Build a standalone query by prepending the prior topic
        standalone = f"{prior_topic} {q}".strip() if prior_topic else q
        return {
            "intent": "follow_up",
            "sub_queries": [standalone],
            "node_visits": visits,
            "trace": trace + ["fast_followup"],
        }

    user_prompt = f"Conversation context:\n{context_str or '(none)'}\n\nLast student query: {q}"
    try:
        raw = generate(INTENT_SYSTEM, user_prompt)
        res = parse_json(raw)
        intent = res.get("intent", "new_topic_explain")
        queries = res.get("queries", [q])
        if not queries:
            queries = [q]
    except Exception:
        intent = "new_topic_explain"
        queries = [q]

    return {
        "intent": intent,
        "sub_queries": queries[:3],
        "node_visits": visits,
        "trace": trace,
    }


def retrieve_node(state: TutorState) -> dict:
    from core.tutor import retrieve
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["retrieve"]

    all_sources = []
    seen_texts = set()
    for sq in state.get("sub_queries", [state["query"]]):
        hits = retrieve(sq, state.get("level", "beginner"))
        for h in hits:
            # Deduplicate by first 60 chars of passage text
            snippet = h["text"][:60]
            if snippet not in seen_texts:
                seen_texts.add(snippet)
                all_sources.append(h)

    # Re-index chunks
    for i, s in enumerate(all_sources, 1):
        s["n"] = i

    return {
        "sources": all_sources[:6],
        "node_visits": visits,
        "trace": trace,
    }


def grade_node(state: TutorState) -> dict:
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["grade"]
    sources = state.get("sources", [])
    retry_count = state.get("retry_count", 0)

    # Check if we have strong sources
    has_strong = any((s.get("score") or 0) >= 0.25 for s in sources)
    if not has_strong and retry_count < 2:
        # Rewrite query for retry
        curr_q = state.get("sub_queries", [state["query"]])[0]
        try:
            rw = generate(
                "Rewrite this technical query with broader academic engineering keywords (output only the rewritten query):",
                curr_q
            ).strip().splitlines()[0]
        except Exception:
            rw = curr_q
        return {
            "sub_queries": [rw],
            "retry_count": retry_count + 1,
            "node_visits": visits,
            "trace": trace + ["retry_rewrite"],
        }

    return {
        "node_visits": visits,
        "trace": trace,
    }


def coverage_node(state: TutorState) -> dict:
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["coverage_check"]
    q = state["query"]
    sources = state.get("sources", [])
    mode = state.get("mode", "text")

    coverage, meta = check_coverage(q, sources, mode=mode)
    return {
        "coverage": coverage,
        "coverage_meta": meta,
        "node_visits": visits,
        "trace": trace,
    }


def _build_history_str(messages: list[dict], max_turns: int = 4) -> str:
    """Build a compact conversation history string for injection into answer prompts."""
    if not messages:
        return ""
    parts = []
    for m in messages[-max_turns * 2:]:   # last N exchanges = 2*N messages
        role = "Student" if m["role"] == "user" else "Tutor"
        if m["role"] == "user":
            content = m.get("content", "")[:300]
        else:
            res_obj = m.get("res") or {}
            content = (
                res_obj.get("answer", "") or
                res_obj.get("reply", "") or ""
            )[:500]
        if content.strip():
            parts.append(f"{role}: {content}")
    return "\n".join(parts)


def route_text_node(state: TutorState) -> dict:
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["route_text"]
    cov = state.get("coverage", "NOT_COVERED")
    q = state["query"]
    sources = state.get("sources", [])
    messages = state.get("messages", [])

    # Build conversation history to inject into every answer prompt
    history_str = _build_history_str(messages[:-1])  # exclude the current turn
    history_block = f"\n\nConversation so far:\n{history_str}" if history_str else ""

    if cov == "COVERED":
        # Grounded from book chunks only
        context = "\n\n".join(f"[{s['n']}] {s['text']}" for s in sources)
        user_prompt = f"Sources:\n{context}{history_block}\n\nStudent Question: {q}"
        raw = generate(BOOK_ANSWER_SYSTEM, user_prompt)
        d = parse_json(raw)
        cited_indices = [n for n in d.get("cited", [1]) if isinstance(n, int) and 1 <= n <= len(sources)] or [1]
        
        # Check if an NPTEL chunk is cited -> provide timestamped YouTube link
        nptel_link = None
        for s in sources:
            if s.get("n") in cited_indices and "nptel" in str(s.get("source", "")).lower():
                ts = s.get("timestamp") or "0s"
                nptel_link = f"https://www.youtube.com/watch?v={s.get('source')}#t={ts}"
                break

        res = {
            "mode": "card",
            "found": True,
            "coverage": "COVERED",
            "source_kind": "books",
            "source_badges": ["From your books"] + (["From NPTEL"] if nptel_link else []),
            "title": d.get("title", "Engineering Concept"),
            "answer": d.get("answer", ""),
            "explanation": d.get("explanation", ""),
            "key_points": d.get("key_points", []),
            "formula": d.get("formula", ""),
            "formula_where": d.get("formula_where", ""),
            "sources": sources,
            "cited": cited_indices,
            "nptel_link": nptel_link,
            "web_used": False,
            "web_sources": [],
        }
        res.update(clean_extras(d))
        return {
            "structured_data": res,
            "answer_text": f"{res['title']}\n\n{res['answer']}\n\n{res['explanation']}",
            "node_visits": visits,
            "trace": trace,
        }

    elif cov == "PARTIAL":
        # Grounded answer for covered part, then separate section "From the web" for missing part
        context = "\n\n".join(f"[{s['n']}] {s['text']}" for s in sources[:3])
        user_prompt = f"Sources:\n{context}{history_block}\n\nStudent Question: {q}"
        raw = generate(PARTIAL_ANSWER_SYSTEM, user_prompt)
        d = parse_json(raw)

        # Web search for the remaining missing aspects
        web_res = web_search(q, k=3)
        web_exp = ""
        if web_res:
            snippets = "\n".join(f"[{i+1}] {r['snippet']}" for i, r in enumerate(web_res))
            w_raw = generate("Summarize the web additions in 2 sentences with [W#] citations:", snippets)
            web_exp = f"\n\n### From the web\n{w_raw}"

        res = {
            "mode": "card",
            "found": True,
            "coverage": "PARTIAL",
            "source_kind": "partial",
            "source_badges": ["From your books", "From the web"],
            "title": d.get("title", "Topic Overview"),
            "answer": d.get("answer", ""),
            "explanation": (d.get("explanation", "") + web_exp).strip(),
            "key_points": d.get("key_points", []),
            "formula": d.get("formula", ""),
            "formula_where": d.get("formula_where", ""),
            "sources": sources,
            "cited": [1],
            "web_used": True,
            "web_sources": web_res,
        }
        res.update(clean_extras(d))
        return {
            "structured_data": res,
            "answer_text": f"{res['title']}\n\n{res['answer']}\n\n{res['explanation']}",
            "node_visits": visits,
            "trace": trace,
        }

    else:  # NOT_COVERED
        # Pure web answer using web_search (up to 5 results)
        web_res = web_search(q, k=5)
        snippets = "\n\n".join(f"[W{i+1}] {r['title']}: {r['snippet']}" for i, r in enumerate(web_res))
        user_prompt = f"Student Question: {q}{history_block}\n\nLive Web Search Snippets:\n{snippets}"
        raw = generate(WEB_ANSWER_SYSTEM, user_prompt)
        d = parse_json(raw)

        res = {
            "mode": "card",
            "found": True,
            "coverage": "NOT_COVERED",
            "source_kind": "web",
            "source_badges": ["From the web"],
            "notice": "Not from your syllabus",
            "title": d.get("title", "Web Topic Overview"),
            "answer": d.get("answer", ""),
            "explanation": d.get("explanation", ""),
            "key_points": d.get("key_points", []),
            "formula": d.get("formula", ""),
            "formula_where": d.get("formula_where", ""),
            "sources": [],
            "cited": [],
            "web_used": True,
            "web_sources": web_res,
        }
        res.update(clean_extras(d))
        return {
            "structured_data": res,
            "answer_text": f"{res['title']}\n\n{res['answer']}\n\n{res['explanation']}",
            "node_visits": visits,
            "trace": trace,
        }


def route_video_node(state: TutorState) -> dict:
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["route_video"]
    cov = state.get("coverage", "NOT_COVERED")
    q = state["query"]

    if cov == "COVERED":
        # Will proceed with local pipeline
        return {
            "final_result": {
                "coverage": "COVERED",
                "kind": "local_video",
                "proceed_render": True,
                "web_videos": [],
            },
            "node_visits": visits,
            "trace": trace,
        }
    elif cov == "PARTIAL":
        # Local video + related web videos row
        wv = find_web_videos(q, top_k=3)
        return {
            "final_result": {
                "coverage": "PARTIAL",
                "kind": "local_video_and_web",
                "proceed_render": True,
                "web_videos": wv.get("videos", []),
            },
            "node_visits": visits,
            "trace": trace,
        }
    else:  # NOT_COVERED
        # No local render! Return web videos directly
        wv = find_web_videos(q, top_k=3)
        return {
            "final_result": {
                "coverage": "NOT_COVERED",
                "status": "done",
                "kind": "web_videos",
                "title": f"Web Videos: {q}",
                "seconds": 0,
                "proceed_render": False,
                "web_videos": wv.get("videos", []),
                "notice": "Web video, not made from your syllabus",
            },
            "node_visits": visits,
            "trace": trace,
        }


def verify_node(state: TutorState) -> dict:
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["verify"]
    res = dict(state.get("structured_data", {}))
    sources = state.get("sources", [])
    cov = state.get("coverage", "COVERED")
    intent = state.get("intent", "")

    # Skip expensive LLM verify for follow-ups and chat replies — saves 1 LLM call
    is_fast_intent = intent in ("follow_up", "smalltalk", "specific_doubt")
    if is_fast_intent or "fast_followup" in state.get("trace", []):
        return {
            "structured_data": res,
            "node_visits": visits,
            "trace": trace + ["verify_skipped"],
        }

    if cov == "COVERED" and sources and res.get("explanation"):
        # LLM entailment check on factual claims
        corpus = " ".join(s["text"] for s in sources[:3])
        v_prompt = f"Corpus:\n{corpus}\n\nExplanation:\n{res['explanation']}\n\nAre any claims ungrounded? Output JSON {{\"unsupported\": []}}"
        try:
            raw = generate("You are a strict grounding verifier.", v_prompt)
            d = parse_json(raw)
            unsupported = d.get("unsupported", [])
            if unsupported:
                res["low_grounding"] = True
        except Exception:
            pass

    return {
        "structured_data": res,
        "node_visits": visits,
        "trace": trace,
    }


def enrich_node(state: TutorState) -> dict:
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["enrich"]
    res = dict(state.get("structured_data", {}))
    ans_text = state.get("answer_text", "")
    intent = state.get("intent", "")

    # Skip enrichment for follow-ups and short answers — saves 1 LLM call (~2-4s)
    is_fast_intent = intent in ("follow_up", "smalltalk")
    is_short_answer = len(ans_text.split()) < 60
    if is_fast_intent or is_short_answer or "fast_followup" in state.get("trace", []):
        return {
            "structured_data": res,
            "enrichment": None,
            "final_result": res,
            "node_visits": visits,
            "trace": trace + ["enrich_skipped"],
        }

    # Run post-verify rich text enrich step
    enrichment = enrich_answer(ans_text)
    if enrichment:
        res["mindmap"] = enrichment.get("mindmap")
        res["highlights"] = enrichment.get("highlights", [])
        res["callouts"] = enrichment.get("callouts", [])

    return {
        "structured_data": res,
        "enrichment": enrichment,
        "final_result": res,
        "node_visits": visits,
        "trace": trace,
    }


def memory_node(state: TutorState) -> dict:
    visits = state.get("node_visits", 0) + 1
    trace = list(state.get("trace", [])) + ["memory"]
    q = state["query"]
    level = state.get("level", "beginner")
    res = state.get("final_result", {})
    topic = res.get("title", "")

    update_learner_profile(q, topic, level)
    log_trace(state)
    return {
        "node_visits": visits,
        "trace": trace,
    }


# ------------------ CONDITIONAL EDGES ------------------

def should_retry_or_coverage(state: TutorState) -> str:
    if state.get("node_visits", 0) >= MAX_NODE_VISITS:
        return "coverage_node"
    if "retry_rewrite" in state.get("trace", []):
        # Clear marker and retry retrieve
        state["trace"].remove("retry_rewrite")
        return "retrieve_node"
    return "coverage_node"


def choose_mode_route(state: TutorState) -> str:
    if state.get("mode") == "video":
        return "route_video_node"
    return "route_text_node"


# ------------------ BUILD GRAPH ------------------

def build_rag_graph() -> StateGraph:
    builder = StateGraph(TutorState)

    builder.add_node("understand_node", understand_node)
    builder.add_node("retrieve_node", retrieve_node)
    builder.add_node("grade_node", grade_node)
    builder.add_node("coverage_node", coverage_node)
    builder.add_node("route_text_node", route_text_node)
    builder.add_node("route_video_node", route_video_node)
    builder.add_node("verify_node", verify_node)
    builder.add_node("enrich_node", enrich_node)
    builder.add_node("memory_node", memory_node)

    builder.set_entry_point("understand_node")

    # If smalltalk detected, exit directly to memory
    builder.add_conditional_edges(
        "understand_node",
        lambda s: "memory_node" if s.get("intent") == "smalltalk" else "retrieve_node",
        {"memory_node": "memory_node", "retrieve_node": "retrieve_node"}
    )

    builder.add_edge("retrieve_node", "grade_node")
    builder.add_conditional_edges(
        "grade_node",
        should_retry_or_coverage,
        {"retrieve_node": "retrieve_node", "coverage_node": "coverage_node"}
    )

    builder.add_conditional_edges(
        "coverage_node",
        choose_mode_route,
        {"route_text_node": "route_text_node", "route_video_node": "route_video_node"}
    )

    builder.add_edge("route_text_node", "verify_node")
    builder.add_edge("verify_node", "enrich_node")
    builder.add_edge("enrich_node", "memory_node")

    builder.add_edge("route_video_node", "memory_node")
    builder.add_edge("memory_node", END)

    return builder.compile()


# Singleton compiled graph instance
GRAPH = build_rag_graph()


def execute_agent_rag(query: str, messages: list[dict], level: str = "beginner", mode: str = "text") -> dict:
    """Entry point executing the LangGraph Agentic RAG core."""
    initial_state: TutorState = {
        "messages": messages,
        "query": query,
        "level": level,
        "mode": mode,
        "intent": "",
        "sub_queries": [query],
        "retry_count": 0,
        "sources": [],
        "coverage": "COVERED",
        "coverage_meta": {},
        "answer_text": "",
        "structured_data": {},
        "web_sources": [],
        "web_videos": [],
        "verification": {},
        "enrichment": None,
        "final_result": {},
        "node_visits": 0,
        "trace": [],
    }
    output_state = GRAPH.invoke(initial_state)
    return output_state.get("final_result", {})
