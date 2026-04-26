from app.config import narrator_prompt_all_sections_enabled
from app.system_prompt import chat_system_content

_FULL = narrator_prompt_all_sections_enabled()


def test_prompt_requires_neutral_failed_perception_narration() -> None:
    prompt = chat_system_content(narrator_config=_FULL)

    assert "resultado **neutro e fechado**" in prompt
    assert "indistinguível** de um lugar que realmente não tinha nada oculto" in prompt
    assert "Evite** vocabulário que insinua segredo não achado" in prompt


def test_prompt_requires_visible_exits_on_arrival() -> None:
    prompt = chat_system_content(narrator_config=_FULL)

    assert "saídas visíveis principais" in prompt


def test_prompt_forbids_hidden_passage_leaks_on_arrival() -> None:
    prompt = chat_system_content(narrator_config=_FULL)

    assert "Regra dura de anti-vazamento na chegada" in prompt
    assert "proibido** mencionar «abertura secreta»" in prompt


def test_prompt_requires_minimal_revisit_narration() -> None:
    prompt = chat_system_content(narrator_config=_FULL)

    assert "ciclos de entra-e-sai entre os mesmos cômodos" in prompt
    assert "resposta curta (1 frase, tipicamente até ~160 caracteres)" in prompt
    assert "um único detalhe" in prompt
    assert "Proibido** em revisit estável: recitar novamente lista de conexões/portas" in prompt
