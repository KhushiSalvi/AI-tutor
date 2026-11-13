"""Coverage check evaluating whether a query is COVERED, PARTIAL, or NOT_COVERED by indexed sources.
Combines reranker scores and an LLM relevance grade.
"""
import yaml
from pathlib import Path
from core.llm import generate, parse_json

CONFIG_FILE = Path("config/coverage.yaml")

DEFAULT_CONFIG = {
    "reranker_covered_min": 0.35,
    "reranker_partial_min": 0.15,
    "min_chunks_covered": 2,
    "min_chunks_partial": 1,
    "use_llm_relevance_check": True,
    "video_ambiguous_preference": "NOT_COVERED",
    "text_ambiguous_preference": "PARTIAL",
}

COVERAGE_GRADE_SYSTEM = """You are a curriculum syllabus evaluator for Electrical & Electronics Engineering.
Determine whether the provided textbook passages answer the MAIN SUBJECT of the student's question.

Return ONLY a JSON object:
{
  "relevance": "FULL" | "PARTIAL" | "NONE",
  "reason": "1 sentence explanation"
}

Guidelines:
- "FULL": The passages directly cover and explain the core principle, formula, circuit, or device asked.
  Examples: asking about MOSFET → passages describe MOSFET structure/operation = FULL.
- "PARTIAL": The passages cover a closely related concept, component, or background theory.
  Examples: asking about differential amplifier → passages describe BJT amplifiers in general = PARTIAL.
- "NONE": The passages are COMPLETELY unrelated to the topic. This is rare.
  Only use NONE if the topic (e.g. cooking recipes, sports) has zero connection to any engineering concept.

Important: Be LENIENT. Engineering topics are interconnected.
If the student asks about a device or circuit that your sources cover even partially, return FULL or PARTIAL — not NONE."""


def load_coverage_config() -> dict:
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
        cfg = dict(DEFAULT_CONFIG)
        if data:
            cfg.update(data)
        return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)


def evaluate_llm_relevance(query: str, sources: list[dict]) -> dict:
    if not sources:
        return {"relevance": "NONE", "reason": "No sources retrieved"}

    context = "\n---\n".join(f"[{i+1}] {s['text'][:350]}" for i, s in enumerate(sources[:3]))
    user_prompt = f"Question: {query}\n\nRetrieved textbook passages:\n{context}"
    try:
        raw = generate(COVERAGE_GRADE_SYSTEM, user_prompt)
        res = parse_json(raw)
        rel = str(res.get("relevance", "PARTIAL")).upper().strip()
        if rel not in {"FULL", "PARTIAL", "NONE"}:
            rel = "PARTIAL"
        return {"relevance": rel, "reason": str(res.get("reason", ""))}
    except Exception as e:
        return {"relevance": "PARTIAL", "reason": f"LLM check failed: {e}"}


def check_coverage(query: str, sources: list[dict], mode: str = "text", config: dict | None = None) -> tuple[str, dict]:
    """Returns coverage status ("COVERED" | "PARTIAL" | "NOT_COVERED") and diagnostic metadata.
    Mode is "text" or "video".

    Score note: the reranker is ms-marco-MiniLM-L-6-v2 which returns raw logit scores
    (typically -10..+10), NOT normalised 0..1 probabilities. The thresholds in
    config/coverage.yaml are set accordingly (covered_min=0.0, partial_min=-3.0).

    Video routing is intentionally lenient: if any relevant chunks exist we try to
    generate a video and let the agent fall back gracefully if content is thin.
    """
    cfg = config or load_coverage_config()
    if not sources:
        return "NOT_COVERED", {"reason": "No sources found", "scores": []}

    scores = [s.get("score") for s in sources if s.get("score") is not None]
    top_score = scores[0] if scores else 0.0
    avg_top2 = sum(scores[:2]) / len(scores[:2]) if scores else 0.0

    llm_grade = {"relevance": "PARTIAL", "reason": "LLM check disabled"}
    if cfg.get("use_llm_relevance_check", True):
        llm_grade = evaluate_llm_relevance(query, sources)

    relevance = llm_grade["relevance"]
    cov_min  = float(cfg.get("reranker_covered_min",  0.0))
    part_min = float(cfg.get("reranker_partial_min", -3.0))
    min_chunks = int(cfg.get("min_chunks_covered", 1))

    meta = {
        "scores": scores,
        "top_score": top_score,
        "avg_top2": avg_top2,
        "llm_relevance": relevance,
        "llm_reason": llm_grade.get("reason", ""),
        "mode": mode,
        "num_sources": len(sources),
    }

    # ── 1. Definite NOT_COVERED ───────────────────────────────────────────
    # Only return NOT_COVERED if the LLM says NONE AND scores are very weak.
    if relevance == "NONE" and top_score < part_min:
        return "NOT_COVERED", meta

    # ── 2. Definite COVERED ──────────────────────────────────────────────
    # LLM says FULL/PARTIAL and score is decent → COVERED
    if relevance in ("FULL", "PARTIAL") and top_score >= cov_min and len(sources) >= min_chunks:
        return "COVERED", meta

    # LLM says FULL regardless of score (trust the LLM more)
    if relevance == "FULL":
        return "COVERED", meta

    # ── 3. Ambiguous / Boundary Zone ─────────────────────────────────────
    if mode == "video":
        # Lean toward COVERED so we try to generate; agent falls back if thin
        pref = cfg.get("video_ambiguous_preference", "COVERED")
        return pref, meta
    else:
        pref = cfg.get("text_ambiguous_preference", "PARTIAL")
        return pref, meta
