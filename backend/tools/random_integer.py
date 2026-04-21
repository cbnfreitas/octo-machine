import json
import secrets

from openai.types.chat import ChatCompletionToolUnionParam

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
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid tool arguments JSON: {e}"})

    try:
        mn = int(args["min"])
        mx = int(args["max"])
        cnt = int(args.get("count", 1))
    except (KeyError, TypeError, ValueError) as e:
        return json.dumps({"error": f"Invalid random_integer args: {e}"})

    return json.dumps(random_integer(mn, mx, cnt))
