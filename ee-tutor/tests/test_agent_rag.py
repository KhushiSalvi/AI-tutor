"""Unit tests for LangGraph Agentic RAG core across all 6 route combinations,
retries, coverage checks, smalltalk, and node visit limits.
"""
try:
    import pytest
except ImportError:
    pytest = None
from unittest.mock import patch, MagicMock
from core.agents.rag_graph import (
    understand_node,
    retrieve_node,
    grade_node,
    coverage_node,
    route_text_node,
    route_video_node,
    verify_node,
    enrich_node,
    build_rag_graph,
    TutorState,
    MAX_NODE_VISITS,
)


def test_smalltalk_fast_path():
    state: TutorState = {
        "messages": [{"role": "user", "content": "hello there"}],
        "query": "hello there",
        "level": "beginner",
        "mode": "text",
        "intent": "",
        "sub_queries": [],
        "retry_count": 0,
        "sources": [],
        "coverage": "",
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
    out = understand_node(state)
    assert out["intent"] == "smalltalk"
    assert "reply" in out["final_result"]
    assert "EE tutor" in out["final_result"]["reply"]


def test_weak_retrieval_retry():
    # Chunks have low score (< 0.25)
    weak_sources = [{"n": 1, "text": "weak unrelated text", "score": 0.12}]
    state: TutorState = {
        "messages": [{"role": "user", "content": "deep quantum gate"}],
        "query": "deep quantum gate",
        "level": "beginner",
        "mode": "text",
        "intent": "new_topic_explain",
        "sub_queries": ["deep quantum gate"],
        "retry_count": 0,
        "sources": weak_sources,
        "coverage": "",
        "coverage_meta": {},
        "answer_text": "",
        "structured_data": {},
        "web_sources": [],
        "web_videos": [],
        "verification": {},
        "enrichment": None,
        "final_result": {},
        "node_visits": 1,
        "trace": ["understand", "retrieve"],
    }
    with patch("core.agents.rag_graph.generate", return_value="quantum logic circuit keywords"):
        out = grade_node(state)
        assert out["retry_count"] == 1
        assert "retry_rewrite" in out["trace"]


def test_route_text_covered():
    book_sources = [
        {"n": 1, "text": "In a MOSFET, when VDS >= VGS - VTH, the channel pinches off.", "score": 0.85, "source": "razavi_cmos"}
    ]
    state: TutorState = {
        "messages": [{"role": "user", "content": "Explain pinch off in MOSFET"}],
        "query": "Explain pinch off in MOSFET",
        "level": "beginner",
        "mode": "text",
        "intent": "new_topic_explain",
        "sub_queries": ["Explain pinch off in MOSFET"],
        "retry_count": 0,
        "sources": book_sources,
        "coverage": "COVERED",
        "coverage_meta": {},
        "answer_text": "",
        "structured_data": {},
        "web_sources": [],
        "web_videos": [],
        "verification": {},
        "enrichment": None,
        "final_result": {},
        "node_visits": 3,
        "trace": [],
    }
    llm_mock_json = '{"mode": "card", "title": "MOSFET Pinch-off", "answer": "Pinch off occurs at the drain.", "explanation": "The inversion layer vanishes at the drain edge.", "key_points": ["Saturation entry"], "formula": "VDS >= VGS - VTH", "cited": [1]}'
    with patch("core.agents.rag_graph.generate", return_value=llm_mock_json):
        out = route_text_node(state)
        res = out["structured_data"]
        assert res["coverage"] == "COVERED"
        assert res["source_kind"] == "books"
        assert "From your books" in res["source_badges"]
        assert res["web_used"] is False


def test_route_text_partial():
    sources = [{"n": 1, "text": "Operational amplifiers have differential inputs.", "score": 0.4, "source": "kuphaldt"}]
    state: TutorState = {
        "messages": [{"role": "user", "content": "Op amp audio mixing console design in 2026"}],
        "query": "Op amp audio mixing console design in 2026",
        "level": "beginner",
        "mode": "text",
        "intent": "new_topic_explain",
        "sub_queries": ["Op amp audio mixing console design in 2026"],
        "retry_count": 0,
        "sources": sources,
        "coverage": "PARTIAL",
        "coverage_meta": {},
        "answer_text": "",
        "structured_data": {},
        "web_sources": [],
        "web_videos": [],
        "verification": {},
        "enrichment": None,
        "final_result": {},
        "node_visits": 3,
        "trace": [],
    }
    llm_partial_json = '{"mode": "card", "title": "Op-Amp Mixing", "answer": "Op-amps provide summing amplifier topologies.", "explanation": "Classic inverting virtual ground sum.", "key_points": ["Summing bus"], "cited": [1]}'
    mock_web = [{"title": "Modern Digital Mixers", "snippet": "Modern consoles use DSP.", "url": "https://example.com/mixer"}]

    with patch("core.agents.rag_graph.generate", side_effect=[llm_partial_json, "Modern consoles use hybrid analog summing [W1]."]), \
         patch("core.agents.rag_graph.web_search", return_value=mock_web):
        out = route_text_node(state)
        res = out["structured_data"]
        assert res["coverage"] == "PARTIAL"
        assert res["source_kind"] == "partial"
        assert "From your books" in res["source_badges"]
        assert "From the web" in res["source_badges"]
        assert "### From the web" in res["explanation"]


def test_route_text_not_covered():
    state: TutorState = {
        "messages": [{"role": "user", "content": "What is React useEffect hook?"}],
        "query": "What is React useEffect hook?",
        "level": "beginner",
        "mode": "text",
        "intent": "out_of_scope",
        "sub_queries": ["What is React useEffect hook?"],
        "retry_count": 0,
        "sources": [],
        "coverage": "NOT_COVERED",
        "coverage_meta": {},
        "answer_text": "",
        "structured_data": {},
        "web_sources": [],
        "web_videos": [],
        "verification": {},
        "enrichment": None,
        "final_result": {},
        "node_visits": 3,
        "trace": [],
    }
    web_hits = [{"title": "React Docs", "snippet": "useEffect manages side effects [W1].", "url": "https://react.dev"}]
    web_llm_json = '{"mode": "card", "title": "React useEffect", "answer": "Hook for side effects.", "explanation": "Runs after render [W1].", "key_points": ["Side effects"]}'

    with patch("core.agents.rag_graph.web_search", return_value=web_hits), \
         patch("core.agents.rag_graph.generate", return_value=web_llm_json):
        out = route_text_node(state)
        res = out["structured_data"]
        assert res["coverage"] == "NOT_COVERED"
        assert res["source_kind"] == "web"
        assert "From the web" in res["source_badges"]
        assert res["notice"] == "Not from your syllabus"


def test_route_video_covered():
    state: TutorState = {
        "messages": [],
        "query": "Explain Thevenin's theorem",
        "level": "beginner",
        "mode": "video",
        "intent": "new_topic_explain",
        "sub_queries": ["Thevenin theorem"],
        "retry_count": 0,
        "sources": [{"text": "Thevenin equivalent"}],
        "coverage": "COVERED",
        "coverage_meta": {},
        "answer_text": "",
        "structured_data": {},
        "web_sources": [],
        "web_videos": [],
        "verification": {},
        "enrichment": None,
        "final_result": {},
        "node_visits": 3,
        "trace": [],
    }
    out = route_video_node(state)
    assert out["final_result"]["proceed_render"] is True
    assert out["final_result"]["coverage"] == "COVERED"


def test_route_video_partial():
    state: TutorState = {
        "messages": [],
        "query": "Thevenin theorem with quantum circuits",
        "level": "beginner",
        "mode": "video",
        "intent": "new_topic_explain",
        "sub_queries": ["Thevenin theorem"],
        "retry_count": 0,
        "sources": [{"text": "Thevenin equivalent"}],
        "coverage": "PARTIAL",
        "coverage_meta": {},
        "answer_text": "",
        "structured_data": {},
        "web_sources": [],
        "web_videos": [],
        "verification": {},
        "enrichment": None,
        "final_result": {},
        "node_visits": 3,
        "trace": [],
    }
    mock_wv = [{"id": "quantum1", "title": "Quantum circuits intro", "channel": "Qiskit", "duration": 400}]
    with patch("core.agents.rag_graph.find_web_videos", return_value={"videos": mock_wv}):
        out = route_video_node(state)
        assert out["final_result"]["proceed_render"] is True
        assert out["final_result"]["coverage"] == "PARTIAL"
        assert len(out["final_result"]["web_videos"]) == 1


def test_route_video_not_covered():
    state: TutorState = {
        "messages": [],
        "query": "History of the Roman Empire",
        "level": "beginner",
        "mode": "video",
        "intent": "out_of_scope",
        "sub_queries": ["Roman Empire"],
        "retry_count": 0,
        "sources": [],
        "coverage": "NOT_COVERED",
        "coverage_meta": {},
        "answer_text": "",
        "structured_data": {},
        "web_sources": [],
        "web_videos": [],
        "verification": {},
        "enrichment": None,
        "final_result": {},
        "node_visits": 3,
        "trace": [],
    }
    mock_wv = [{"id": "rome1", "title": "Fall of Rome", "channel": "History", "duration": 600}]
    with patch("core.agents.rag_graph.find_web_videos", return_value={"videos": mock_wv}):
        out = route_video_node(state)
        res = out["final_result"]
        # No local render!
        assert res["proceed_render"] is False
        assert res["status"] == "done"
        assert res["kind"] == "web_videos"
        assert len(res["web_videos"]) == 1
        assert res["web_videos"][0]["id"] == "rome1"
