import json
import secrets

from openai.types.chat import ChatCompletionToolUnionParam

from app.logging_config import logger, yellow_tool

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
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        logger.warning(
            "%s bad JSON arguments_json=%r err=%s",
            yellow_tool("toss_coin"),
            arguments_json,
            e,
        )
        return json.dumps({"error": f"Invalid tool arguments JSON: {e}"})

    try:
        cnt = int(args.get("count", 1))
    except (TypeError, ValueError) as e:
        logger.warning(
            "%s bad count parsed=%r arguments_json=%r err=%s",
            yellow_tool("toss_coin"),
            args,
            arguments_json,
            e,
        )
        return json.dumps({"error": f"Invalid toss_coin args: {e}"})

    result = toss_coin(cnt)
    logger.info("[%s] count=%s -> results=%s", yellow_tool("toss_coin"), cnt, result["results"])
    return json.dumps(result)
