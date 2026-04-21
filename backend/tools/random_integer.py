import secrets
from typing import Any, cast

from openai.types.chat import ChatCompletionToolUnionParam

from .invoke import invoke_tool

TOOL_SYSTEM_INSTRUCTION = (
    "Quando o jogador precisar de inteiros aleatórios num intervalo (dados, sorteio, escolhas "
    "numéricas etc.), chame `random_integer`. Responda usando somente os números retornados—nunca "
    "invente inteiros."
)

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "random_integer",
        "description": (
            "Gera inteiros aleatórios no intervalo fechado [min, max], inclusive. "
            "Chame quando precisar de inteiros imprevisíveis, dados, sorteios ou números num "
            "intervalo—não invente valores. Usa fonte criptograficamente forte."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "min": {
                    "type": "integer",
                    "description": "Valor mínimo (inclusive).",
                },
                "max": {
                    "type": "integer",
                    "description": "Valor máximo (inclusive).",
                },
                "count": {
                    "type": "integer",
                    "description": "Quantos inteiros independentes gerar.",
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
