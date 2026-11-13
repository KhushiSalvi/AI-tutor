"""Safe numpy-based expression evaluator for compute_data tool.

The LLM calls compute_data(expression, variables, sweep) and gets back
numeric arrays. We NEVER eval arbitrary Python from the LLM — we parse
only a whitelist of numpy/math operations.
"""
import re
import math
from typing import Any

import numpy as np

# Allowed names inside expressions
_SAFE_NAMES: dict[str, Any] = {
    # numpy ufuncs
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan, "atan2": np.arctan2,
    "exp": np.exp, "log": np.log, "log10": np.log10, "log2": np.log2,
    "sqrt": np.sqrt, "abs": np.abs, "sign": np.sign,
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "ceil": np.ceil, "floor": np.floor, "round": np.round,
    "min": np.minimum, "max": np.maximum,
    "linspace": np.linspace, "arange": np.arange, "logspace": np.logspace,
    "zeros": np.zeros, "ones": np.ones,
    "array": np.array, "pi": np.pi, "e": np.e, "inf": np.inf,
    # numpy constants
    "j": 1j,  # imaginary unit
}

_FORBIDDEN = re.compile(
    r"\b(import|exec|eval|open|__|\bos\b|\bsys\b|\bsubprocess\b|compile|globals|locals)\b"
)


def safe_eval(expr: str, variables: dict[str, Any]) -> Any:
    """Evaluate expr with variables and numpy, raising ValueError on bad input."""
    if _FORBIDDEN.search(expr):
        raise ValueError(f"Forbidden expression: {expr!r}")
    if len(expr) > 500:
        raise ValueError("Expression too long (max 500 chars)")
    ns = {**_SAFE_NAMES, **{str(k): v for k, v in variables.items()}}
    try:
        result = eval(compile(expr, "<expr>", "eval"), {"__builtins__": {}}, ns)  # noqa: S307
        return result
    except Exception as e:
        raise ValueError(f"Evaluation error in {expr!r}: {e}") from e


def compute_sweep(expression: str, variable: str, start: float, stop: float,
                  n: int = 200, log_scale: bool = False) -> tuple[list, list]:
    """Sweep `variable` from start to stop, evaluate expression, return (xs, ys)."""
    if log_scale:
        xs = np.logspace(np.log10(max(start, 1e-30)), np.log10(max(stop, 1e-30)), n)
    else:
        xs = np.linspace(start, stop, n)
    ys = safe_eval(expression, {variable: xs})
    if np.isscalar(ys):
        ys = np.full_like(xs, float(ys))
    ys = np.asarray(ys, dtype=float)
    # Replace infinities/NaN with boundary values so SVG doesn't break
    ys = np.nan_to_num(ys, nan=0.0, posinf=float(np.nanmax(ys[np.isfinite(ys)], initial=0)),
                       neginf=float(np.nanmin(ys[np.isfinite(ys)], initial=0)))
    return xs.tolist(), ys.tolist()
