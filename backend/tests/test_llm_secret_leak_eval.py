from __future__ import annotations

import json
import os

import pytest
from openai import OpenAI

from app.system_prompt import chat_system_content

from tests.narrator_prompt_full_app_config import FULL_NARRATOR_APP_CONFIG


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


RUN_REAL_LLM_TEST = _env_flag_enabled("RUN_REAL_LLM_LEAK_TEST")
RUN_REAL_LLM_CONCISION_TEST = _env_flag_enabled("RUN_REAL_LLM_CONCISION_TEST")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")

pytestmark = pytest.mark.skipif(
    not RUN_REAL_LLM_TEST or not OPENAI_API_KEY,
    reason=(
        "Real LLM leak test is opt-in. Set RUN_REAL_LLM_LEAK_TEST=1 and OPENAI_API_KEY "
        "(or OPEN_AI_API_KEY)."
    ),
)


def test_arrival_narration_does_not_leak_hidden_connection() -> None:
    client = OpenAI(api_key=OPENAI_API_KEY)
    narrator_model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    judge_model = os.getenv("OPENAI_JUDGE_MODEL", "gpt-5-mini")

    move_payload = {
        "place_name": "Vestíbulo",
        "revisit": False,
        "basic_description": (
            "Um espaço circular silencioso, banhado pela luz da lua que entra por um vitral alto. "
            "Uma escada curva domina o ambiente."
        ),
        "connections": [
            {
                "to": "Despensa",
                "how": "porta sudoeste",
                "destination_hidden_until_discovery": False,
                "seems_traversable_now": True,
            },
            {
                "to": "São Principal",
                "how": "passagem leste",
                "destination_hidden_until_discovery": False,
                "seems_traversable_now": True,
            },
            {
                "to": "Quarto do Max",
                "how": "abertura secreta discreta",
                "destination_hidden_until_discovery": True,
                "seems_traversable_now": False,
            },
        ],
        "player_facing_summary": (
            "Um espaço circular silencioso, banhado pela luz da lua que entra por um vitral alto. "
            "Uma escada curva domina o ambiente.\n\n"
            "A partir daqui você pode ir para porta sudoeste e passagem leste."
        ),
    }

    narrator_user_prompt = (
        "### PLAYER_INTENT (jogador -> narradora)\n"
        "eu vou pro próximo aposento\n\n"
        "### ENGINE_CONTEXT (engine -> narradora)\n"
        "- Lugar atual: Vestíbulo\n"
        "- Fadiga: baixa\n"
        "- Tempo in-game: 00:06\n\n"
        "### RESULTADO_MOVE_JSON (factual)\n"
        f"{json.dumps(move_payload, ensure_ascii=False)}\n\n"
        "Tarefa: narre a chegada ao Vestíbulo em 1 parágrafo curto, em PT-BR, segunda pessoa. "
        "Não vaze conexões ocultas. Não cite regras."
    )

    narrator_resp = client.chat.completions.create(
        model=narrator_model,
        messages=[
            {"role": "system", "content": chat_system_content(app_config=FULL_NARRATOR_APP_CONFIG)},
            {"role": "user", "content": narrator_user_prompt},
        ],
    )
    narration = (narrator_resp.choices[0].message.content or "").strip()
    assert narration, "Narrator model returned empty output"

    judge_prompt = (
        "Você é uma LLM juíza. Avalie se a narração vazou conexão oculta.\n"
        "Conexão oculta proibida de aparecer: "
        "\"Quarto do Max\" / \"abertura secreta discreta\" / qualquer menção de passagem secreta.\n"
        "A narração pode citar apenas conexões visíveis: \"porta sudoeste\" e \"passagem leste\".\n\n"
        f"NARRAÇÃO:\n{narration}\n\n"
        "Responda estritamente em JSON com este formato:\n"
        '{"leak": boolean, "reason": "texto curto"}'
    )
    judge_resp = client.chat.completions.create(
        model=judge_model,
        messages=[{"role": "user", "content": judge_prompt}],
        response_format={"type": "json_object"},
    )
    raw_judgement = (judge_resp.choices[0].message.content or "").strip()
    data = json.loads(raw_judgement)

    assert isinstance(data, dict), "Judge output is not a JSON object"
    assert data.get("leak") is False, f"LLM judge flagged leak: {data}"


@pytest.mark.skipif(
    not RUN_REAL_LLM_CONCISION_TEST or not OPENAI_API_KEY,
    reason=(
        "Real LLM concision test is opt-in. Set RUN_REAL_LLM_CONCISION_TEST=1 and OPENAI_API_KEY "
        "(or OPEN_AI_API_KEY)."
    ),
)
def test_revisit_ping_pong_is_concise_and_not_redundant() -> None:
    client = OpenAI(api_key=OPENAI_API_KEY)
    narrator_model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    judge_model = os.getenv("OPENAI_JUDGE_MODEL", "gpt-5-mini")

    previous_narration = (
        "Você empurra a porta e entra no vestíbulo. O espaço é circular, a luz do vitral cai nas pedras, "
        "a escadaria curva domina o centro. Há porta sudoeste para a despensa, passagem leste para a sala "
        "principal e porta sul para a cozinha."
    )
    move_payload = {
        "place_name": "Vestíbulo",
        "revisit": True,
        "basic_description": (
            "Um espaço circular silencioso, banhado pela luz da lua que entra por um vitral alto. "
            "Uma escada curva domina o ambiente."
        ),
        "details": (
            "A escada começa a oeste e curva-se para o norte até um pequeno mezanino com porta ornamentada. "
            "O espaço ecoa levemente. Segredo difícil: pequena abertura de ventilação quase invisível."
        ),
        "connections": [
            {
                "to": "Despensa",
                "how": "porta sudoeste",
                "destination_hidden_until_discovery": False,
                "seems_traversable_now": True,
            },
            {
                "to": "São Principal",
                "how": "passagem leste",
                "destination_hidden_until_discovery": False,
                "seems_traversable_now": True,
            },
            {
                "to": "Cozinha",
                "how": "porta sul",
                "destination_hidden_until_discovery": False,
                "seems_traversable_now": True,
            },
        ],
        "player_facing_summary": (
            "Um espaço circular silencioso, banhado pela luz da lua que entra por um vitral alto. "
            "Uma escada curva domina o ambiente.\n\n"
            "A partir daqui você pode ir para porta sudoeste, passagem leste e porta sul."
        ),
    }

    narrator_user_prompt = (
        "### PLAYER_INTENT\n"
        "eu vou para o vestíbulo\n\n"
        "### CONTEXTO_RECENTE\n"
        f"- Narração anterior imediata:\n{previous_narration}\n"
        "- O jogador está fazendo entra-e-sai entre cozinha e vestíbulo.\n"
        "- Nada relevante mudou no cenário físico.\n\n"
        "### RESULTADO_MOVE_JSON\n"
        f"{json.dumps(move_payload, ensure_ascii=False)}\n\n"
        "Tarefa: narre este retorno ao vestíbulo de forma breve e natural, em PT-BR."
    )

    narrator_resp = client.chat.completions.create(
        model=narrator_model,
        messages=[
            {"role": "system", "content": chat_system_content(app_config=FULL_NARRATOR_APP_CONFIG)},
            {"role": "user", "content": narrator_user_prompt},
        ],
    )
    narration = (narrator_resp.choices[0].message.content or "").strip()
    assert narration, "Narrator model returned empty output"
    assert len(narration) <= 260, (
        "Revisit narration is too long for a no-change ping-pong move: "
        f"{len(narration)} chars"
    )

    judge_prompt = (
        "Você é uma LLM juíza de estilo narrativo em RPG.\n"
        "Critérios de aprovação (todos obrigatórios):\n"
        "1) A resposta de retorno (revisit) deve ser curta e sucinta.\n"
        "2) Não deve re-descrever longamente elementos estáveis do cômodo.\n"
        "3) Deve soar como continuação da cena, não como nova descrição completa.\n"
        "4) Se nada mudou, deve evitar listar conexões/portas novamente.\n"
        "5) Se usar ambiência, no máximo um detalhe curto.\n\n"
        f"NARRAÇÃO ANTERIOR (já dita):\n{previous_narration}\n\n"
        f"NARRAÇÃO AVALIADA:\n{narration}\n\n"
        "Responda estritamente em JSON:\n"
        '{"ok": boolean, "reason": "texto curto"}'
    )
    judge_resp = client.chat.completions.create(
        model=judge_model,
        messages=[{"role": "user", "content": judge_prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads((judge_resp.choices[0].message.content or "").strip())

    assert isinstance(data, dict), "Judge output is not a JSON object"
    assert data.get("ok") is True, f"LLM judge rejected revisit concision: {data}"
