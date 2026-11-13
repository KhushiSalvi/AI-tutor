"""JSON Schema validation for lesson plan output from the LLM.
Provides a lightweight second gate after sanitize_scene() to catch top-level
structural problems (missing 'found', wrong types) before they reach the renderer.
"""
import json
try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

LESSON_PLAN_SCHEMA = {
    "type": "object",
    "required": ["found", "video_title", "scenes"],
    "properties": {
        "found": {"type": "boolean"},
        "video_title": {"type": "string", "maxLength": 80},
        "reason": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "narration", "visual"],
                "properties": {
                    "title":     {"type": "string", "maxLength": 80},
                    "narration": {"type": "string", "minLength": 5},
                    "citation":  {"type": "string"},
                    "visual": {
                        "type": "object",
                        "required": ["type"],
                        "properties": {
                            "type": {"type": "string", "enum": [
                                "title_bullets","formula_build","flow","compare",
                                "circuit_flow","waveform_plot","pipeline_timing",
                                "logic_truth","block_diagram",
                                "phasor_diagram","bode_plot","transistor_iv","state_machine"
                            ]}
                        }
                    }
                }
            }
        }
    }
}


def validate_lesson_plan(plan: dict) -> tuple[bool, str]:
    """Returns (ok, error_message). If jsonschema not installed, always returns (True, '')."""
    if not _HAS_JSONSCHEMA:
        return True, ""
    try:
        jsonschema.validate(plan, LESSON_PLAN_SCHEMA)
        return True, ""
    except jsonschema.ValidationError as e:
        return False, e.message
    except Exception as e:
        return False, str(e)
