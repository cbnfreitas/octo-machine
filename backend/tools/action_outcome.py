import secrets
from typing import Any

from openai.types.chat import ChatCompletionToolUnionParam

from .invoke import invoke_tool

# d100 roll (1-100). Columns: Sucesso Crítico 1%, Sucesso, Falha, Falha Crítica 1% (same for all rows).
_DIFFICULTY_ORDER: tuple[str, ...] = (
    "muito_facil",
    "facil",
    "medio",
    "dificil",
    "muito_dificil",
)

# (success_max, fail_max) on 1-100: r==1 crit success; 2..success_max success; success_max+1..fail_max fail; fail_max+1..99 fail; 100 crit fail
# muito_facil: 94% success -> 2-95, 4% fail -> 96-99
_DIFFICULTY_D100_BOUNDS: dict[str, tuple[int, int]] = {
    "muito_facil": (95, 99),
    "facil": (80, 99),
    "medio": (50, 99),
    "dificil": (20, 99),
    "muito_dificil": (5, 99),
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


def _outcome_from_d100(difficulty: str, r: int) -> str:
    if not 1 <= r <= 100:
        raise ValueError("r must be 1..100")
    if r == 1:
        return "sucesso_critico"
    if r == 100:
        return "falha_critica"
    success_max, fail_max = _DIFFICULTY_D100_BOUNDS[difficulty]
    if r <= success_max:
        return "sucesso"
    if r <= fail_max:
        return "falha"
    raise RuntimeError("d100 mapping out of range")


def _roll_outcome(difficulty: str) -> tuple[str, int]:
    r = secrets.randbelow(100) + 1
    return _outcome_from_d100(difficulty, r), r


for _d, (_s, _f) in _DIFFICULTY_D100_BOUNDS.items():
    assert 1 < _s < _f == 99, _d


TOOL_SYSTEM_INSTRUCTION = (
    "Para ações incertas (teste, disputa, risco, oposição), chame `action_outcome` com **`skill`** "
    "(texto livre: o que está a ser tentado; reservado para regras futuras) e **`difficulty`** entre "
    "`muito_facil`, `facil`, `medio`, `dificil`, `muito_dificil` - alinhado ao **risco real** na cena "
    "(mortal/giro completo: pelo menos `medio`, nunca `facil`). O sorteio usa d100 (1-100); 1% sucesso "
    "crítico, 1% falha crítica; o meio segue a tabela do nível. Em testes de percepção/investigação: "
    "`facil` só para ação muito específica no ponto certo; `medio` para busca focada com incerteza; "
    "`dificil`/`muito_dificil` para pistas sutis em baixa luz/pressão/obstrução. Em **falha** ou "
    "**falha crítica** de investigação, narra inconclusão **sem** confirmar segredos nem repetir na "
    "prosa nomes de suspeitas que só existem no texto do `skill` (evita vazar pistas ao jogador). "
    "Integre o resultado na narração."
)

_DIFFICULTY_ENUM = list(_DIFFICULTY_ORDER)

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "action_outcome",
        "description": (
            "Resolve uma ação incerta com d100 por nível: muito_facil, facil, medio, dificil, muito_dificil."
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
                        "Nível de risco real da manobra na cena. Mortal/giro completo/salto com rotação "
                        "nunca é facil: use pelo menos medio (subir para dificil se pressão, fadiga ou "
                        "terreno forem ruins). muito_facil/facil só para gestos quase triviais."
                    ),
                },
            },
            "required": ["skill", "difficulty"],
        },
    },
}


def action_outcome(*, skill: str, difficulty: str) -> dict[str, object]:
    outcome, roll_d100 = _roll_outcome(difficulty)
    return {
        "skill": skill,
        "difficulty": difficulty,
        "difficulty_display_pt": _DIFFICULTY_LABELS_PT[difficulty],
        "probability_roll_d100": roll_d100,
        "outcome": outcome,
        "outcome_display_pt": _OUTCOME_DISPLAY_PT[outcome],
    }


def run(arguments_json: str) -> str:
    def execute(args: dict[str, Any]) -> dict[str, object]:
        raw_skill = args["skill"]
        if not isinstance(raw_skill, str):
            raise ValueError("skill must be a string")
        difficulty = args["difficulty"]
        if not isinstance(difficulty, str) or difficulty not in _DIFFICULTY_D100_BOUNDS:
            raise ValueError("difficulty must be one of the allowed enum values")
        return action_outcome(skill=raw_skill, difficulty=difficulty)

    return invoke_tool(
        "action_outcome",
        arguments_json,
        execute,
        log_line=lambda r: "skill=%r difficulty=%s d100=%s outcome=%s (%s)"
        % (
            r["skill"],
            r["difficulty"],
            r["probability_roll_d100"],
            r["outcome"],
            r["outcome_display_pt"],
        ),
    )
