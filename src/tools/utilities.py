"""Restricted AST calculation and timezone-aware datetime utilities."""

from __future__ import annotations

import ast
import logging
import operator
from datetime import datetime
from typing import Any
import zoneinfo

from src.config import get_config

logger = logging.getLogger(__name__)

# Allowed binary operators
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Allowed unary operators
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

MAX_EXPONENT = 1000


def _safe_eval_ast(node: ast.AST) -> float | int:
    """Recursively evaluate an AST expression with strict operator and node limits."""
    if isinstance(node, ast.Expression):
        return _safe_eval_ast(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in _UNARY_OPS:
            operand = _safe_eval_ast(node.operand)
            return _UNARY_OPS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in _BIN_OPS:
            left = _safe_eval_ast(node.left)
            right = _safe_eval_ast(node.right)

            # Prevent denial-of-service via huge exponents
            if op_type is ast.Pow:
                if abs(right) > MAX_EXPONENT:
                    raise ValueError(f"Exponent exceeds safe limit of {MAX_EXPONENT}.")

            try:
                result = _BIN_OPS[op_type](left, right)
            except ZeroDivisionError:
                raise ValueError("Division by zero is undefined.")

            # Check if result is finite
            if isinstance(result, float) and (result != result or abs(result) == float("inf")):
                raise ValueError("Calculation resulted in non-finite value (inf/nan).")

            return result

        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")

    raise ValueError(f"Restricted evaluator rejected expression construct: {type(node).__name__}")


def calculate(expression: str) -> dict[str, Any]:
    """
    Evaluate basic arithmetic expressions using a restricted AST evaluator.
    Strictly forbids eval(), exec(), function calls, variables, or imports.
    """
    clean_expr = str(expression).strip()
    if not clean_expr:
        return {"ok": False, "tool": "calculate", "error": "Expression cannot be empty."}

    if len(clean_expr) > 200:
        return {"ok": False, "tool": "calculate", "error": "Expression exceeds maximum length of 200 chars."}

    try:
        parsed = ast.parse(clean_expr, mode="eval")
        result = _safe_eval_ast(parsed)
        return {
            "ok": True,
            "tool": "calculate",
            "result": {
                "expression": clean_expr,
                "value": result,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "tool": "calculate",
            "error": f"Evaluation error: {exc}",
        }


def get_current_datetime() -> dict[str, Any]:
    """
    Return current date and time in the configured APP_TIMEZONE,
    formatted cleanly with ISO-8601 timestamp and timezone name.
    """
    cfg = get_config()
    tz_str = cfg.app_timezone

    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        logger.warning("Invalid timezone '%s', defaulting to UTC.", tz_str)
        tz = zoneinfo.ZoneInfo("UTC")
        tz_str = "UTC"

    now = datetime.now(tz)

    return {
        "ok": True,
        "tool": "get_current_datetime",
        "result": {
            "readable": now.strftime("%A, %B %d, %Y %I:%M:%S %p"),
            "iso": now.isoformat(),
            "timezone": tz_str,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
        },
    }
