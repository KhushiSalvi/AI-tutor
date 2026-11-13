"""Tests for core/video/templates.py — all 9 animation templates + quality-gate logic.

Runs without pytest (uses stdlib unittest). No browser or ffmpeg needed: we only
inspect the returned HTML strings for required structure.
"""
import unittest
from unittest.mock import MagicMock, patch

try:
    import pytest
except ImportError:
    pytest = None  # noqa

from core.video.templates import (
    title_bullets, formula_build, flow, compare,
    circuit_flow, waveform_plot, pipeline_timing, logic_truth, block_diagram,
    render_scene_html, TEMPLATES,
)
from core.video.lesson_plan import (
    sanitize_scene, sanitize_scenes,
    estimate_seconds, trim_to_budget,
    _sanitize_circuit_flow, _sanitize_waveform_plot,
    _sanitize_pipeline_timing, _sanitize_logic_truth, _sanitize_block_diagram,
    MIN_SCENES, MAX_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has(html: str, *fragments: str) -> bool:
    return all(f in html for f in fragments)


def _scene(title="Test Scene", narration="This is a test narration for the scene.", citation="book p.1", **kw):
    return dict(title=title, narration=narration, citation=citation, **kw)


# ---------------------------------------------------------------------------
# Original 4 templates
# ---------------------------------------------------------------------------

class TestOriginalTemplates(unittest.TestCase):

    def test_title_bullets_renders_title_and_bullets(self):
        sc = _scene(visual={"type": "title_bullets", "bullets": ["Point A", "Point B"]},
                    bullets=["Point A", "Point B"])
        html = title_bullets({**sc, **sc["visual"]}, 1, 3)
        self.assertIn("Test Scene", html)
        self.assertIn("Point A", html)
        self.assertIn("Point B", html)
        self.assertIn("data-start", html)

    def test_formula_build_renders_tokens(self):
        sc = _scene(visual={"type": "formula_build", "formula": "V = I R", "formula_where": "V volts, I amps, R ohms"})
        html = formula_build({**sc, **sc["visual"]}, 1, 3)
        self.assertIn("V", html)
        self.assertIn("tok", html)   # CSS class for token spans
        self.assertIn("ohms", html)

    def test_flow_renders_nodes_and_particle(self):
        sc = _scene(visual={"type": "flow", "nodes": ["Fetch", "Decode", "Execute"]})
        html = flow({**sc, **sc["visual"]}, 2, 5)
        self.assertIn("Fetch", html)
        self.assertIn("particle", html)

    def test_compare_renders_both_columns(self):
        sc = _scene(visual={"type": "compare",
                             "left":  {"label": "NMOS", "points": ["n-channel", "faster"]},
                             "right": {"label": "PMOS", "points": ["p-channel", "slower"]}})
        html = compare({**sc, **sc["visual"]}, 1, 2)
        self.assertIn("NMOS", html)
        self.assertIn("PMOS", html)
        self.assertIn("slideL", html)
        self.assertIn("slideR", html)


# ---------------------------------------------------------------------------
# 5 New templates
# ---------------------------------------------------------------------------

class TestCircuitFlow(unittest.TestCase):

    def test_renders_all_components(self):
        sc = _scene(visual={"type": "circuit_flow",
                             "components": ["R1 10ohm", "C1 10uF", "LED"],
                             "label_in": "Vin", "label_out": "Vout"})
        html = circuit_flow({**sc, **sc["visual"]}, 1, 4)
        self.assertIn("R1 10ohm", html)
        self.assertIn("C1 10uF", html)
        self.assertIn("LED", html)
        self.assertIn("Vin", html)
        self.assertIn("Vout", html)
        self.assertIn("dot", html)       # current particle

    def test_fallback_on_one_component(self):
        sc = _scene(visual={"type": "circuit_flow", "components": ["R1"]},
                    bullets=["single component"])
        html = circuit_flow({**sc, **sc["visual"]}, 1, 2)
        # Should fall back to title_bullets since <2 components
        self.assertIn("Test Scene", html)

    def test_clamps_to_five_components(self):
        sc = _scene(visual={"type": "circuit_flow",
                             "components": ["A","B","C","D","E","F","G"]})
        html = circuit_flow({**sc, **sc["visual"]}, 1, 2)
        self.assertNotIn("F", html)
        self.assertNotIn("G", html)


class TestWaveformPlot(unittest.TestCase):

    def _render(self, shape, **kw):
        sc = _scene(visual={"type": "waveform_plot", "shape": shape,
                             "x_label": "Time (s)", "y_label": "V(t)", **kw})
        return waveform_plot({**sc, **sc["visual"]}, 1, 3)

    def test_sine_contains_polyline(self):
        html = self._render("sine")
        self.assertIn("<polyline", html)
        self.assertIn("stroke-dashoffset", html)

    def test_rc_charge_renders(self):
        html = self._render("rc_charge")
        self.assertIn("<polyline", html)

    def test_square_renders(self):
        html = self._render("square")
        self.assertIn("<polyline", html)

    def test_sawtooth_renders(self):
        html = self._render("sawtooth")
        self.assertIn("<polyline", html)

    def test_axes_labels_appear(self):
        html = self._render("sine")
        self.assertIn("Time (s)", html)
        self.assertIn("V(t)", html)

    def test_highlight_marker_included_when_set(self):
        html = self._render("sine", highlight_x=0.5)
        self.assertIn("f7768e", html)   # marker colour


class TestPipelineTiming(unittest.TestCase):

    def test_all_stage_labels_present(self):
        sc = _scene(visual={"type": "pipeline_timing",
                             "stages": ["IF","ID","EX","MEM","WB"],
                             "cycles": 7, "instructions": 3})
        html = pipeline_timing({**sc, **sc["visual"]}, 1, 2)
        for s in ["IF","ID","EX","MEM","WB"]:
            self.assertIn(s, html)

    def test_instruction_labels_present(self):
        sc = _scene(visual={"type": "pipeline_timing",
                             "stages": ["IF","ID","EX"],
                             "cycles": 5, "instructions": 2})
        html = pipeline_timing({**sc, **sc["visual"]}, 1, 3)
        self.assertIn("I1", html)
        self.assertIn("I2", html)

    def test_clamps_cycles_to_nine(self):
        sc = _scene(visual={"type": "pipeline_timing",
                             "stages": ["A","B","C"],
                             "cycles": 20, "instructions": 2})
        # sanitize_pipeline_timing should clamp cycles to 9
        result = _sanitize_pipeline_timing(sc["visual"])
        self.assertEqual(result["cycles"], 9)

    def test_clamps_instructions_to_four(self):
        sc = _scene(visual={"type": "pipeline_timing",
                             "stages": ["A","B"],
                             "cycles": 6, "instructions": 10})
        result = _sanitize_pipeline_timing(sc["visual"])
        self.assertEqual(result["instructions"], 4)


class TestLogicTruth(unittest.TestCase):

    def _truth_rows(self, gate, inputs, expected_outputs):
        sc = _scene(visual={"type": "logic_truth", "gate": gate,
                             "inputs": inputs, "output": "Y"})
        html = logic_truth({**sc, **sc["visual"]}, 1, 3)
        # Check all expected output values appear in the HTML
        for val in expected_outputs:
            self.assertIn(str(val), html)
        return html

    def test_and_gate(self):
        # AND: 0,0->0; 0,1->0; 1,0->0; 1,1->1
        html = self._truth_rows("AND", ["A","B"], [0, 1])
        self.assertIn("AND Gate", html)

    def test_or_gate(self):
        html = self._truth_rows("OR", ["A","B"], [0, 1])
        self.assertIn("OR Gate", html)

    def test_not_gate_single_input(self):
        sc = _scene(visual={"type": "logic_truth", "gate": "NOT",
                             "inputs": ["A"], "output": "Y"})
        html = logic_truth({**sc, **sc["visual"]}, 1, 2)
        self.assertIn("NOT Gate", html)
        # NOT A=0 -> 1, A=1 -> 0
        self.assertIn("1", html)
        self.assertIn("0", html)

    def test_xor_gate(self):
        html = self._truth_rows("XOR", ["A","B"], [0, 1])
        self.assertIn("XOR Gate", html)

    def test_invalid_gate_defaults_to_and(self):
        result = _sanitize_logic_truth({"gate": "BOGUS", "inputs": ["A","B"], "output": "Y"})
        self.assertEqual(result["gate"], "AND")

    def test_truth_table_values_computed_correctly(self):
        """NAND(0,0)=1, NAND(0,1)=1, NAND(1,0)=1, NAND(1,1)=0"""
        sc = _scene(visual={"type": "logic_truth", "gate": "NAND",
                             "inputs": ["A","B"], "output": "Y"})
        html = logic_truth({**sc, **sc["visual"]}, 1, 2)
        # Count occurrences: NAND has three 1s and one 0 in output column
        # We just check both values appear (green for 1, red for 0)
        self.assertIn("9ece6a", html)   # green (output=1)
        self.assertIn("f7768e", html)   # red   (output=0)


class TestBlockDiagram(unittest.TestCase):

    def test_all_blocks_present(self):
        sc = _scene(visual={"type": "block_diagram",
                             "blocks": [{"id":"cpu","label":"CPU"},
                                        {"id":"mem","label":"Memory"},
                                        {"id":"io", "label":"I/O"}],
                             "edges": [{"from":"cpu","to":"mem","label":"data bus"}],
                             "highlight": "cpu"})
        html = block_diagram({**sc, **sc["visual"]}, 1, 3)
        self.assertIn("CPU", html)
        self.assertIn("Memory", html)
        self.assertIn("I/O", html)

    def test_edge_label_appears(self):
        sc = _scene(visual={"type": "block_diagram",
                             "blocks": [{"id":"a","label":"A"},{"id":"b","label":"B"}],
                             "edges": [{"from":"a","to":"b","label":"control"}]})
        html = block_diagram({**sc, **sc["visual"]}, 1, 2)
        self.assertIn("control", html)

    def test_highlight_adds_glow_animation(self):
        sc = _scene(visual={"type": "block_diagram",
                             "blocks": [{"id":"x","label":"X"},{"id":"y","label":"Y"}],
                             "edges": [], "highlight": "x"})
        html = block_diagram({**sc, **sc["visual"]}, 1, 2)
        self.assertIn("glow", html)

    def test_fallback_on_no_valid_blocks(self):
        sc = _scene(visual={"type": "block_diagram", "blocks": []},
                    bullets=["fallback bullet"])
        html = block_diagram({**sc, **sc["visual"]}, 1, 2)
        # Should fall back to title_bullets
        self.assertIn("Test Scene", html)

    def test_clamps_to_six_blocks(self):
        blocks = [{"id": f"b{i}", "label": f"Block{i}"} for i in range(10)]
        result = _sanitize_block_diagram({"blocks": blocks, "edges": []})
        self.assertEqual(len(result["blocks"]), 6)


# ---------------------------------------------------------------------------
# render_scene_html dispatch + fallback
# ---------------------------------------------------------------------------

class TestRenderSceneHtml(unittest.TestCase):

    def test_dispatches_all_nine_types(self):
        types_and_visuals = {
            "title_bullets":   {"bullets": ["A"]},
            "formula_build":   {"formula": "E = mc2", "formula_where": "E energy"},
            "flow":            {"nodes": ["A","B","C"]},
            "compare":         {"left": {"label":"L","points":["x"]},
                                "right": {"label":"R","points":["y"]}},
            "circuit_flow":    {"components": ["R","C"], "label_in":"Vin", "label_out":"Vout"},
            "waveform_plot":   {"shape": "sine", "x_label":"t", "y_label":"V"},
            "pipeline_timing": {"stages":["IF","ID"], "cycles":4, "instructions":2},
            "logic_truth":     {"gate":"AND","inputs":["A","B"],"output":"Y"},
            "block_diagram":   {"blocks":[{"id":"a","label":"A"},{"id":"b","label":"B"}],
                                "edges":[{"from":"a","to":"b","label":""}]},
        }
        for vtype, visual in types_and_visuals.items():
            with self.subTest(vtype=vtype):
                sc = _scene(visual={"type": vtype, **visual})
                html = render_scene_html(sc, 1, 5)
                self.assertIn("<!doctype html>", html, f"{vtype} didn't return valid HTML")
                self.assertIn("Test Scene", html, f"{vtype} missing title")

    def test_unknown_type_falls_back_to_title_bullets(self):
        sc = _scene(visual={"type": "completely_unknown", "bullets": ["Fallback"]})
        html = render_scene_html(sc, 1, 1)
        self.assertIn("<!doctype html>", html)

    def test_all_nine_types_registered_in_templates_dict(self):
        # 13 templates: original 9 + 4 added in Phase A (phasor, bode, transistor_iv, state_machine)
        expected = {
            "title_bullets", "formula_build", "flow", "compare",
            "circuit_flow", "waveform_plot", "pipeline_timing", "logic_truth", "block_diagram",
            "phasor_diagram", "bode_plot", "transistor_iv", "state_machine",
        }
        self.assertEqual(set(TEMPLATES.keys()), expected)


# ---------------------------------------------------------------------------
# Sanitize helpers for new template types
# ---------------------------------------------------------------------------

class TestSanitizeNewTypes(unittest.TestCase):

    def test_circuit_flow_requires_two_components(self):
        self.assertIsNone(_sanitize_circuit_flow({"components": ["R1"]}))

    def test_circuit_flow_clamps_five(self):
        result = _sanitize_circuit_flow({"components": ["A","B","C","D","E","F","G"]})
        self.assertEqual(len(result["components"]), 5)

    def test_waveform_invalid_shape_becomes_sine(self):
        result = _sanitize_waveform_plot({"shape": "TRIANGLE"})
        self.assertEqual(result["shape"], "sine")

    def test_waveform_valid_shapes_pass_through(self):
        for s in ["sine","rc_charge","square","sawtooth"]:
            result = _sanitize_waveform_plot({"shape": s})
            self.assertEqual(result["shape"], s)

    def test_pipeline_timing_fallback_stages(self):
        result = _sanitize_pipeline_timing({})
        self.assertIn("IF", result["stages"])

    def test_logic_truth_clamps_inputs_to_two(self):
        result = _sanitize_logic_truth({"gate":"AND","inputs":["A","B","C","D"],"output":"Y"})
        self.assertEqual(len(result["inputs"]), 2)

    def test_block_diagram_drops_invalid_blocks(self):
        blocks = [{"id":"a","label":"A"}, {"id":"","label":"B"}, {"label":"C"}]
        result = _sanitize_block_diagram({"blocks": blocks, "edges": []})
        self.assertEqual(len(result["blocks"]), 1)   # only "a" is valid

    def test_sanitize_scene_routes_new_types(self):
        for vtype, extra in [
            ("circuit_flow",   {"components":["R","C"],"label_in":"V"}),
            ("waveform_plot",  {"shape":"sine"}),
            ("pipeline_timing",{"stages":["IF","ID"],"cycles":4,"instructions":2}),
            ("logic_truth",    {"gate":"OR","inputs":["A","B"],"output":"Y"}),
            ("block_diagram",  {"blocks":[{"id":"a","label":"A"},{"id":"b","label":"B"}],"edges":[]}),
        ]:
            with self.subTest(vtype=vtype):
                sc = {"title": "T", "narration": "N", "citation": "c",
                      "visual": {"type": vtype, **extra}}
                result = sanitize_scene(dict(sc))
                self.assertEqual(result["visual"]["type"], vtype)


# ---------------------------------------------------------------------------
# Lesson plan helpers: estimate_seconds, trim_to_budget
# ---------------------------------------------------------------------------

class TestLessonPlanHelpers(unittest.TestCase):

    def _make_scenes(self, n_words_each, count):
        return [{"narration": " ".join(["word"] * n_words_each),
                 "title": f"S{i}", "citation": "c", "visual": {"type": "title_bullets", "bullets": []}}
                for i in range(count)]

    def test_estimate_seconds_correct(self):
        scenes = self._make_scenes(50, 3)   # 50 words / 2.5 wps = 20s per scene → 60s total
        total = estimate_seconds(scenes)
        self.assertAlmostEqual(total, 60.0, delta=1.0)

    def test_trim_keeps_min_scenes(self):
        scenes = self._make_scenes(300, 10)  # 300 words each = 120s each → way over budget
        trimmed = trim_to_budget(scenes, max_seconds=MAX_SECONDS, min_scenes=MIN_SCENES)
        self.assertGreaterEqual(len(trimmed), MIN_SCENES)

    def test_trim_preserves_first_and_last(self):
        scenes = self._make_scenes(200, 8)
        trimmed = trim_to_budget(scenes, max_seconds=100, min_scenes=3)
        self.assertEqual(trimmed[0]["title"], scenes[0]["title"])
        self.assertEqual(trimmed[-1]["title"], scenes[-1]["title"])


# ---------------------------------------------------------------------------
# Quality gate logic (unit-tested without a real browser)
# ---------------------------------------------------------------------------

class TestQualityGate(unittest.TestCase):

    def test_large_png_passes(self):
        from core.video.animate import _quality_check
        page = MagicMock()
        # Return a 20 KB PNG (content-rich)
        page.screenshot.return_value = b"x" * 20_000
        self.assertTrue(_quality_check(page, "<html></html>", 2.0))

    def test_tiny_png_fails(self):
        from core.video.animate import _quality_check
        page = MagicMock()
        # Return a 5 KB PNG (blank/solid)
        page.screenshot.return_value = b"x" * 5_000
        self.assertFalse(_quality_check(page, "<html></html>", 2.0))

    def test_exception_in_quality_check_returns_true(self):
        """Quality gate failure must be non-fatal."""
        from core.video.animate import _quality_check
        page = MagicMock()
        page.set_content.side_effect = RuntimeError("browser crash")
        result = _quality_check(page, "<html></html>", 2.0)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
