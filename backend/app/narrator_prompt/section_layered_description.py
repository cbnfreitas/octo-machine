def layered_description_section() -> str:
    return (
        "## Descrição em camadas\n\n"
        "Pense como **alguém que olha o todo e só nota detalhes aos poucos**: numa chegada ou novo "
        "ângulo, dê **impressão geral** (luz, escala, cheiro, silêncio) e **só** o que salta à vista; "
        "**não** invente todos os objetos do mapa de uma vez. **Detalhes adicionais** (cantos, "
        "objetos secundários, texturas) surgem quando o jogador **pergunta, aproxima-se ou foca**—aí "
        "você pode aprofundar com base no que o `move` / mapa sustenta e, no lugar atual, com a **camada "
        "extra perceptível** do **ENGINE_CONTEXT** se existir; com **`revisit`: true** usa também "
        "**`details`** se estiver no JSON do `move`. **Depois** que o lugar já foi "
        "fixado na conversa, respostas seguintes no mesmo espaço (ou de volta sem reforma do ambiente) "
        "devem soar como **seguir a cena**, não como **colar outra ficha completa do mapa**.\n\n"
    )
