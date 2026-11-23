import ast
import math
import operator
import json
from pathlib import Path

from langchain_core.tools import tool
from src.config_loader import load_user_info


# =========================================================
# Calculator
# =========================================================

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "lcm": math.lcm,
    "min": min,
    "max": max,
}

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def _evaluate(node):
    """Safely evaluate an approved mathematical AST node."""

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("Only numeric constants are allowed.")

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)

        if op_type not in _OPERATORS:
            raise ValueError("Unsupported operator.")

        left = _evaluate(node.left)
        right = _evaluate(node.right)

        # Prevent extremely large exponent calculations
        if op_type == ast.Pow:
            if abs(right) > 1000:
                raise ValueError("Exponent is too large.")

            if abs(left) > 1e100 and right > 1:
                raise ValueError("Result would be excessively large.")

        result = _OPERATORS[op_type](left, right)

        return result

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)

        if op_type not in _OPERATORS:
            raise ValueError("Unsupported unary operator.")

        return _OPERATORS[op_type](_evaluate(node.operand))

    elif isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]

        raise ValueError(f"Unknown constant: {node.id}")

    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Invalid function call.")

        function_name = node.func.id

        if function_name not in _FUNCTIONS:
            raise ValueError(f"Unsupported function: {function_name}")

        if node.keywords:
            raise ValueError("Keyword arguments are not supported.")

        args = [_evaluate(arg) for arg in node.args]

        return _FUNCTIONS[function_name](*args)

    else:
        raise ValueError(
            f"Unsupported expression: {type(node).__name__}"
        )


@tool
def calculate(expression: str) -> str:
    """Calculate mathematical expressions accurately using a safe arithmetic evaluator.

    Supports arithmetic (+, -, *, /, //, %, **), parentheses,
    unary signs, and mathematical functions such as sqrt, abs,
    round, floor, ceil, sin, cos, tan, log, log10, exp,
    factorial, gcd, lcm, min, and max.

    Supports mathematical constants pi, e, and tau.

    Examples:
    - 125 * 48
    - (25 + 15) / 2
    - sqrt(144)
    - 2 ** 10
    - sin(pi / 2)
    - log10(1000)
    - factorial(5)
    - gcd(48, 18)

    Use this tool for arithmetic and mathematical calculations
    requiring accurate results. Expressions are evaluated
    without executing arbitrary Python code.
    """

    try:
        if len(expression) > 500:
            return "Error: Expression is too long."

        tree = ast.parse(expression, mode="eval")

        result = _evaluate(tree.body)

        if isinstance(result, float):
            if not math.isfinite(result):
                return "Error: Result is not finite."

            # Remove unnecessary floating-point noise
            if result.is_integer():
                result = int(result)

        return str(result)

    except ZeroDivisionError:
        return "Error: Division by zero."

    except OverflowError:
        return "Error: Result is too large."

    except Exception as e:
        return f"Calculation error: {e}"


# =========================================================
# Persistent User Information
# =========================================================

USER_INFO_PATH = Path("user_info.json")


@tool
def update_user_info(name: str = None, description: str = None) -> str:
    """Update the user's persistent information.

    Use this tool only when the user explicitly asks to remember,
    save, change, or update their personal information.

    Parameters:
        name: The user's preferred name.
        description: Information about the user, including interests,
                    preferences, background, or other relevant details.

    Only update the fields explicitly provided.
    Preserve existing fields that are not being updated.
    The JSON file must contain only 'name' and 'description'.
    """
    try:
        # Load existing information using the existing function
        current_info = load_user_info()

        # Ensure we have the expected structure
        user_info = {
            "name": current_info.get("name", "Unnamed"),
            "description": current_info.get("description", "")
        }

        # Update only explicitly provided fields
        if name is not None:
            name = name.strip()
            if name:
                user_info["name"] = name

        if description is not None:
            description = description.strip()
            if description:
                user_info["description"] = description

        # Save exactly two keys
        with USER_INFO_PATH.open("w", encoding="utf-8") as f:
            json.dump(user_info, f, indent=4, ensure_ascii=False)

        return "User information updated successfully."

    except Exception as e:
        return f"Failed to update user information: {type(e).__name__}: {e}"