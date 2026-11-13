"""Unit tests for Rich Text Output enricher and sanitizers."""
try:
    import pytest
except ImportError:
    pytest = None

from core.enrich import (
    sanitize_mindmap,
    sanitize_highlights,
    sanitize_callouts,
    count_sentences,
)


def test_count_sentences():
    assert count_sentences("One sentence.") == 1
    assert count_sentences("One. Two! Three?") == 3
    assert count_sentences("Sentence one. Sentence two. Sentence three. Sentence four!") == 4
    assert count_sentences("") == 0


def test_sanitize_highlights_exact_substring():
    full_text = "The transconductance gm represents the sensitivity of drain current ID to gate-source voltage VGS."
    raw_highlights = [
        {"text": "transconductance gm", "kind": "term"},
        {"text": "drain current ID", "kind": "term"},
        {"text": "Hall effect sensor", "kind": "term"},  # NOT in text! Must be rejected
        {"text": "gate-source voltage VGS", "kind": "formula"},
        {"text": "transconductance gm", "kind": "term"},  # duplicate
    ]
    cleaned = sanitize_highlights(raw_highlights, full_text)
    texts = [h["text"] for h in cleaned]

    assert "transconductance gm" in texts
    assert "drain current ID" in texts
    assert "gate-source voltage VGS" in texts
    assert "Hall effect sensor" not in texts  # Rejected!
    assert len(cleaned) == 3  # Deduplicated and non-substring dropped


def test_sanitize_highlights_invalid_kind_fallback():
    full_text = "Notice that saturation occurs when VDS exceeds VGS minus VTH."
    raw = [{"text": "saturation occurs", "kind": "invented_kind"}]
    cleaned = sanitize_highlights(raw, full_text)
    assert len(cleaned) == 1
    assert cleaned[0]["kind"] == "term"  # Fallback to term


def test_sanitize_mindmap_depth_and_node_limits():
    # Build deep/wide tree
    deep_tree = {
        "label": "Root Topic For MOSFET",
        "children": [
            {
                "label": "Level 1 Branch One",
                "children": [
                    {
                        "label": "Level 2 Sub Branch",
                        "children": [
                            {"label": "Level 3 Too Deep Child", "children": []}
                        ]
                    }
                ]
            }
        ]
    }
    cleaned = sanitize_mindmap(deep_tree)
    assert cleaned is not None
    assert cleaned["label"] == "Root Topic For MOSFET"
    # Max depth is 3 (level 0, 1, 2). Level 3 must be truncated
    lvl1 = cleaned["children"][0]
    lvl2 = lvl1["children"][0]
    assert len(lvl2["children"]) == 0  # Truncated!


def test_sanitize_mindmap_label_max_words():
    tree = {
        "label": "This is a very long label with way too many words to be clean",
        "children": []
    }
    cleaned = sanitize_mindmap(tree)
    assert cleaned is not None
    assert len(cleaned["label"].split()) <= 4


def test_sanitize_callouts_limits():
    raw_callouts = [
        {"kind": "important", "title": "Check Vds", "text": "Always ensure VDS > VGS - VTH."},
        {"kind": "watch_out", "title": "Breakdown", "text": "Exceeding VBD destroys the oxide layer."},
        {"kind": "exam_tip", "title": "Gate Question", "text": "Expect questions on body effect."},
        {"kind": "remember", "title": "Linear Mode", "text": "In triode, current varies with VDS."},
        {"kind": "extra", "title": "Excess", "text": "This should be dropped because max is 4."},
    ]
    cleaned = sanitize_callouts(raw_callouts)
    assert len(cleaned) == 4
    assert cleaned[0]["kind"] == "important"
    assert cleaned[1]["kind"] == "watch_out"
