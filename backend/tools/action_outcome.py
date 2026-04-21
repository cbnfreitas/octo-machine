import secrets
from typing import Any

from openai.types.chat import ChatCompletionToolUnionParam

from .invoke import invoke_tool

_OUTCOME_WEIGHTS: list[tuple[str, int]] = [
    ("falha_critica", 5),
    ("falha", 10),
    ("sucesso", 80),
    ("sucesso_critico", 5),
]

_OUTCOME_DISPLAY_PT: dict[str, str] = {
    "falha_critica": "falha crítica",
    "falha": "falha",
    "sucesso": "sucesso",
    "sucesso_critico": "sucesso crítico",
}

_TOTAL = sum(w for _, w in _OUTCOME_WEIGHTS)
assert _TOTAL == 100

TOOL_SYSTEM_INSTRUCTION = (
    "Para ações que exijam acaso (disputa, teste de habilidade fora do trivial, risco, oposição), "
    "chame `action_outcome` com um texto **curto** em `context`: quem age, o quê e como. "
    "A ferramenta devolve um dos quatro resultados ponderados (falha crítica 5%, falha 10%, "
    "sucesso 80%, sucesso crítico 5%). Narre o desfecho coerente com esse resultado."
)

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "action_outcome",
        "description": (
            "Resolve uma ação incerta com resultado aleatório ponderado: falha crítica (5%), "
            "falha (10%), sucesso (80%), sucesso crítico (5%). Envie um contexto breve da cena."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": (
                        "Resumo curto da ação: quem, o quê, como (ex.: "
                        "'Você tenta arrombar a porta de madeira com o ombro')."
                    ),
                },
            },
            "required": ["context"],
        },
    },
}


def _roll_outcome() -> str:
    r = secrets.randbelow(_TOTAL)
    acc = 0
    for name, w in _OUTCOME_WEIGHTS:
        acc += w
        if r < acc:
            return name
    raise RuntimeError("weighted roll out of range")


def action_outcome(context: str) -> dict[str, object]:
    trimmed = context.strip()
    outcome = _roll_outcome()
    return {
        "outcome": outcome,
        "outcome_display_pt": _OUTCOME_DISPLAY_PT[outcome],
        "action_context": trimmed,
    }


def run(arguments_json: str) -> str:
    def execute(args: dict[str, Any]) -> dict[str, object]:
        ctx = args["context"]
        if not isinstance(ctx, str) or not ctx.strip():
            raise ValueError("context must be a non-empty string")
        return action_outcome(ctx)

    return invoke_tool(
        "action_outcome",
        arguments_json,
        execute,
        log_line=lambda r: "context=%r outcome=%s (%s)"
        % (
            r["action_context"],
            r["outcome"],
            r["outcome_display_pt"],
        ),
    )
