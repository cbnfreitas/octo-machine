import secrets
from typing import Any, cast

from openai.types.chat import ChatCompletionToolUnionParam

from .invoke import invoke_tool

TOOL_SYSTEM_INSTRUCTION = (
    "When the user asks for a coin flip, heads/tails (cara/coroa), yes/no from a fair "
    "binary chance, or multiple independent flips, call `toss_coin`. "
    "`True` means heads (cara); `False` means tails (coroa). Answer only from the tool output."
)

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "toss_coin",
        "description": (
            "Fair random coin flip(s). Each result is independent: True = heads (cara), "
            "False = tails (coroa). Do not guess outcomes—call this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "How many independent flips (default 1).",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
        },
    },
}


def toss_coin(count: int = 1) -> dict[str, object]:
    count = max(1, min(100, count))
    results = [secrets.randbelow(2) == 1 for _ in range(count)]
    return {"results": results, "heads_is_true": True}


def run(arguments_json: str) -> str:
    def execute(args: dict[str, Any]) -> dict[str, object]:
        return toss_coin(int(args.get("count", 1)))

    return invoke_tool(
        "toss_coin",
        arguments_json,
        execute,
        log_line=lambda r: f"count={len(cast(list[Any], r['results']))} -> results={r['results']}",
    )
