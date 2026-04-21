import secrets
from typing import Any, cast

from openai.types.chat import ChatCompletionToolUnionParam

from .invoke import invoke_tool

TOOL_SYSTEM_INSTRUCTION = (
    "Quando o jogador pedir cara ou coroa, sorteio binário justo (sim/não) ou várias jogadas "
    "independentes, chame `toss_coin`. `True` = cara; `False` = coroa. Responda só com a saída da "
    "ferramenta."
)

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "toss_coin",
        "description": (
            "Cara ou coroa justo(s). Cada resultado é independente: True = cara, False = coroa. "
            "Não chute—use esta ferramenta."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Quantas jogadas independentes (padrão 1).",
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
