"""Calibrate coverage check thresholds on eval/coverage_set.jsonl.
Evaluates accuracy, confusion matrix, and tunes config/coverage.yaml.
"""
import os
import sys
from pathlib import Path

# Set offline mode so HuggingFace does not attempt network calls inside sandbox
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json
from core.retrieval.coverage import check_coverage, load_coverage_config

from core.tutor import retrieve


def load_dataset():
    path = ROOT / "eval" / "coverage_set.jsonl"
    if not path.exists():
        print(f"Error: dataset {path} does not exist.")
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def run_calibration(sample_limit=None):
    items = load_dataset()
    if not items:
        print("No items to evaluate.")
        return

    if sample_limit:
        items = items[:sample_limit]

    print(f"Loaded {len(items)} questions for coverage calibration.", flush=True)
    print("Pre-fetching retrieval results...", flush=True)

    cached_retrievals = []
    for i, item in enumerate(items, 1):
        q = item["query"]
        try:
            sources = retrieve(q, level="advanced")
        except Exception as e:
            sources = []
        cached_retrievals.append((item, sources))
        print(f"  [{i}/{len(items)}] Retrieved {len(sources)} chunks for: {q[:40]}...", flush=True)

    # Threshold grid sweep
    cov_candidates = [0.25, 0.30, 0.35, 0.40, 0.45]
    part_candidates = [0.10, 0.15, 0.20]

    best_acc = -1.0
    best_params = {}
    best_cm = {}

    for c_min in cov_candidates:
        for p_min in part_candidates:
            if p_min >= c_min:
                continue

            test_cfg = {
                "reranker_covered_min": c_min,
                "reranker_partial_min": p_min,
                "min_chunks_covered": 2,
                "min_chunks_partial": 1,
                "use_llm_relevance_check": False,  # fast heuristic calibration
                "video_ambiguous_preference": "NOT_COVERED",
                "text_ambiguous_preference": "PARTIAL",
            }

            cm = {
                ("COVERED", "COVERED"): 0,
                ("COVERED", "NOT_COVERED"): 0,
                ("COVERED", "PARTIAL"): 0,
                ("NOT_COVERED", "COVERED"): 0,
                ("NOT_COVERED", "NOT_COVERED"): 0,
                ("NOT_COVERED", "PARTIAL"): 0,
            }

            correct = 0
            for item, sources in cached_retrievals:
                expected = item["expected"]
                pred, _ = check_coverage(item["query"], sources, mode="text", config=test_cfg)
                # Group partial into covered or not covered based on expected
                key = (expected, pred)
                cm[key] = cm.get(key, 0) + 1
                if expected == pred or (expected == "COVERED" and pred == "PARTIAL"):
                    correct += 1

            acc = correct / len(cached_retrievals)
            if acc > best_acc:
                best_acc = acc
                best_params = {"reranker_covered_min": c_min, "reranker_partial_min": p_min}
                best_cm = cm

    print("\n==========================================")
    print("CALIBRATION RESULTS")
    print("==========================================")
    print(f"Best Accuracy: {best_acc*100:.2f}%")
    print(f"Optimal Parameters: {best_params}")
    print("\nConfusion Matrix (Expected vs Predicted):")
    print(f"  True COVERED -> Pred COVERED:     {best_cm.get(('COVERED', 'COVERED'), 0)}")
    print(f"  True COVERED -> Pred PARTIAL:     {best_cm.get(('COVERED', 'PARTIAL'), 0)}")
    print(f"  True COVERED -> Pred NOT_COVERED: {best_cm.get(('COVERED', 'NOT_COVERED'), 0)}")
    print(f"  True NOT_COVERED -> Pred NOT_COV: {best_cm.get(('NOT_COVERED', 'NOT_COVERED'), 0)}")
    print(f"  True NOT_COVERED -> Pred PARTIAL: {best_cm.get(('NOT_COVERED', 'PARTIAL'), 0)}")
    print(f"  True NOT_COVERED -> Pred COVERED: {best_cm.get(('NOT_COVERED', 'COVERED'), 0)}")
    print("==========================================\n")
    return best_params, best_acc


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_calibration(limit)
