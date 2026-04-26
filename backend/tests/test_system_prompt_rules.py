from app.system_prompt import chat_system_content


def test_prompt_requires_neutral_failed_perception_narration() -> None:
    prompt = chat_system_content()

    assert "resultado **neutro e fechado**" in prompt
    assert "indistinguível** de um lugar que realmente não tinha nada oculto" in prompt
    assert "Evite** vocabulário que insinua segredo não achado" in prompt


def test_prompt_requires_visible_exits_on_arrival() -> None:
    prompt = chat_system_content()

    assert "saídas visíveis principais" in prompt


def test_prompt_forbids_hidden_passage_leaks_on_arrival() -> None:
    prompt = chat_system_content()

    assert "Regra dura de anti-vazamento na chegada" in prompt
    assert "proibido** mencionar «abertura secreta»" in prompt
