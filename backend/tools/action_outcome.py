import secrets
from typing import Any

from openai.types.chat import ChatCompletionToolUnionParam

from .invoke import invoke_tool

# Order matches table columns: Sucesso Crítico, Sucesso, Falha, Falha Crítica (weights in millionths).
_OUTCOME_KEYS: tuple[str, ...] = (
    "sucesso_critico",
    "sucesso",
    "falha",
    "falha_critica",
)

_DIFFICULTY_WEIGHTS_MILLIONTHS: dict[str, tuple[int, int, int, int]] = {
    "muito_facil": (10_000, 940_000, 49_999, 1),
    "facil": (1_000, 799_000, 199_990, 10),
    "medio": (100, 499_900, 499_900, 100),
    "dificil": (10, 199_990, 799_000, 1_000),
    "muito_dificil": (1, 49_999, 940_000, 10_000),
}

_DIFFICULTY_LABELS_PT: dict[str, str] = {
    "muito_facil": "Muito Fácil",
    "facil": "Fácil",
    "medio": "Médio",
    "dificil": "Difícil",
    "muito_dificil": "Muito Difícil",
}

_OUTCOME_DISPLAY_PT: dict[str, str] = {
    "falha_critica": "falha crítica",
    "falha": "falha",
    "sucesso": "sucesso",
    "sucesso_critico": "sucesso crítico",
}

_MILLION = 1_000_000
for _diff, _tuple in _DIFFICULTY_WEIGHTS_MILLIONTHS.items():
    assert sum(_tuple) == _MILLION, _diff

TOOL_SYSTEM_INSTRUCTION = (
    "Para ações incertas (teste, disputa, risco, oposição), chame `action_outcome` com **`skill`** "
    "(texto livre: o que está a ser tentado; reservado para regras futuras) e **`difficulty`** entre "
    "`muito_facil`, `facil`, `medio`, `dificil`, `muito_dificil` — alinhado à dificuldade que já "
    "introduziste na ficção. A ferramenta sorteia sucesso crítico, sucesso, falha ou falha crítica "
    "com as probabilidades da tabela desse nível. Integre o resultado na narração."
)

_DIFFICULTY_ENUM = list(_DIFFICULTY_WEIGHTS_MILLIONTHS.keys())

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "action_outcome",
        "description": (
            "Resolve uma ação incerta com sorte ponderado por nível de dificuldade: muito_facil, facil, "
            "medio, dificil, muito_dificil (ver probabilidades no system prompt da ferramenta)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": (
                        "Etiqueta livre da manobra ou competência (ex.: 'saltar para o parapesto'). "
                        "Ainda não altera o sorteio; serve para registo."
                    ),
                },
                "difficulty": {
                    "type": "string",
                    "enum": _DIFFICULTY_ENUM,
                    "description": (
                        "Muito Fácil = muito_facil; Fácil = facil; Médio = medio; Difícil = dificil; "
                        "Muito Difícil = muito_dificil."
                    ),
                },
            },
            "required": ["skill", "difficulty"],
        },
    },
}


def _roll_outcome(difficulty: str) -> str:
    weights_tuple = _DIFFICULTY_WEIGHTS_MILLIONTHS[difficulty]
    pairs = list(zip(_OUTCOME_KEYS, weights_tuple, strict=True))
    total = sum(w for _, w in pairs)
    r = secrets.randbelow(total)
    acc = 0
    for name, w in pairs:
        acc += w
        if r < acc:
            return name
    raise RuntimeError("weighted roll out of range")


def action_outcome(*, skill: str, difficulty: str) -> dict[str, object]:
    outcome = _roll_outcome(difficulty)
    return {
        "skill": skill,
        "difficulty": difficulty,
        "difficulty_display_pt": _DIFFICULTY_LABELS_PT[difficulty],
        "outcome": outcome,
        "outcome_display_pt": _OUTCOME_DISPLAY_PT[outcome],
    }


def run(arguments_json: str) -> str:
    def execute(args: dict[str, Any]) -> dict[str, object]:
        raw_skill = args["skill"]
        if not isinstance(raw_skill, str):
            raise ValueError("skill must be a string")
        difficulty = args["difficulty"]
        if not isinstance(difficulty, str) or difficulty not in _DIFFICULTY_WEIGHTS_MILLIONTHS:
            raise ValueError("difficulty must be one of the allowed enum values")
        return action_outcome(skill=raw_skill, difficulty=difficulty)

    return invoke_tool(
        "action_outcome",
        arguments_json,
        execute,
        log_line=lambda r: "skill=%r difficulty=%s outcome=%s (%s)"
        % (
            r["skill"],
            r["difficulty"],
            r["outcome"],
            r["outcome_display_pt"],
        ),
    )
