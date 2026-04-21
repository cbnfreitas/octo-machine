import secrets
from typing import Any, cast

from openai.types.chat import ChatCompletionToolUnionParam

from .invoke import invoke_tool

TOOL_SYSTEM_INSTRUCTION = (
    "When the user wants random integers in a range (dice, lottery, numeric picks, etc.), "
    "call `random_integer`. Answer using only the returned numbers—never invent integers."
)

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "random_integer",
        "description": (
            "Generate random integers in a closed range [min, max], inclusive. "
            "Call this whenever the user asks for random/unpredictable integers, "
            "dice, lottery draws, or numbers in a range — do not make up values. "
            "Uses a cryptographically strong source."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "min": {
                    "type": "integer",
                    "description": "Minimum value (inclusive).",
                },
                "max": {
                    "type": "integer",
                    "description": "Maximum value (inclusive).",
                },
                "count": {
                    "type": "integer",
                    "description": "How many independent integers to generate.",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["min", "max"],
        },
    },
}


def random_integer(min_v: int, max_v: int, count: int = 1) -> dict[str, object]:
    if min_v > max_v:
        min_v, max_v = max_v, min_v
    count = max(1, min(100, count))
    span = max_v - min_v + 1
    numbers = [min_v + secrets.randbelow(span) for _ in range(count)]
    return {"numbers": numbers, "min": min_v, "max": max_v}


def run(arguments_json: str) -> str:
    def execute(args: dict[str, Any]) -> dict[str, object]:
        return random_integer(
            int(args["min"]),
            int(args["max"]),
            int(args.get("count", 1)),
        )

    return invoke_tool(
        "random_integer",
        arguments_json,
        execute,
        log_line=lambda r: f"min={r['min']} max={r['max']} count={len(cast(list[Any], r['numbers']))} -> numbers={r['numbers']}",
    )
