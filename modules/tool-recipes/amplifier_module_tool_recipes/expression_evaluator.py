"""Safe expression evaluator for recipe conditions.

Supports simple boolean expressions with:
- Comparison: == !=
- Boolean operators: and or
- Variable references: {{variable}}
- String literals: 'value' or "value"

NO eval() or exec() - safe string parsing only.
"""

import re
from typing import Any


class ExpressionError(Exception):
    """Error evaluating condition expression."""

    pass


def evaluate_condition(expression: str, context: dict[str, Any]) -> bool:
    """Evaluate a condition expression against context.

    Args:
        expression: Condition string (e.g., "{{status}} == 'success'")
        context: Dictionary of variable values

    Returns:
        True if condition passes, False otherwise

    Raises:
        ExpressionError: On undefined variables or invalid syntax
    """
    if not expression or not expression.strip():
        return True  # Empty condition = always true

    # Substitute variables first
    substituted = _substitute_variables(expression, context)

    # Parse and evaluate the expression
    return _evaluate_expression(substituted.strip())


def _substitute_variables(expression: str, context: dict[str, Any]) -> str:
    """Replace {{variable}} references with their values."""
    pattern = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")

    def replace_var(match: re.Match) -> str:
        var_path = match.group(1)
        value = _resolve_variable(var_path, context)
        if value is None:
            raise ExpressionError(f"Undefined variable: {var_path}")
        # Convert to string representation for comparison
        if isinstance(value, str):
            return f"'{value}'"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return pattern.sub(replace_var, expression)


def _resolve_variable(path: str, context: dict[str, Any]) -> Any:
    """Resolve dotted variable path (e.g., 'step.id')."""
    parts = path.split(".")
    value = context
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def _evaluate_expression(expr: str) -> bool:
    """Evaluate substituted expression to boolean."""
    expr = expr.strip()

    # Handle 'or' (lowest precedence)
    if " or " in expr:
        parts = expr.split(" or ", 1)
        return _evaluate_expression(parts[0]) or _evaluate_expression(parts[1])

    # Handle 'and' (higher precedence than or)
    if " and " in expr:
        parts = expr.split(" and ", 1)
        return _evaluate_expression(parts[0]) and _evaluate_expression(parts[1])

    # Handle comparison operators
    for op in ("==", "!="):
        if op in expr:
            left, right = expr.split(op, 1)
            left_val = _parse_value(left.strip())
            right_val = _parse_value(right.strip())
            if op == "==":
                return left_val == right_val
            return left_val != right_val

    # Handle boolean literals
    if expr.lower() == "true":
        return True
    if expr.lower() == "false":
        return False

    raise ExpressionError(f"Invalid expression syntax: {expr}")


def _parse_value(token: str) -> str | bool:
    """Parse a value token (string literal or boolean)."""
    token = token.strip()

    # String literal with single quotes
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1]

    # String literal with double quotes
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]

    # Boolean literals
    if token.lower() == "true":
        return True
    if token.lower() == "false":
        return False

    # Unquoted value (treat as string after variable substitution)
    return token
