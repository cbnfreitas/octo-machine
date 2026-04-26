from app.config import AppConfig

from tools.move import (
    STARTING_PLACE_NAME,
    fixed_intro_ui_enabled,
    game_map_basename,
    get_game_fixed_intro,
    get_narrator_opening_note,
    get_player_narrative_filters,
    narrator_opening_turn_reference,
)


def fixed_intro_context_section(app_config: AppConfig) -> str:
    """Controlled by ``AppConfig.include_fixed_intro_context``
    """
    fixed = get_game_fixed_intro().strip()
    if not fixed:
        return ""
    ref = narrator_opening_turn_reference(app_config)
    intro_shown = fixed_intro_ui_enabled(app_config)
    if app_config.include_tools_move:
        if intro_shown:
            second_reply = (
                f"**Não** repita esse texto na **segunda** mensagem (a que responde à ficha oculta {ref}). "
                "Nessa resposta use só `move` para o lugar inicial e narre o que o "
                "personagem percebe **neste** espaço, sem reencenar a escalada da janela salvo **no máximo** uma "
                "frase de transição.\n\n"
            )
        else:
            second_reply = (
                f"**Não** repita esse texto na íntegra na **primeira** mensagem gerada para a UI (a que responde à "
                f"ficha oculta {ref}). Nessa resposta use só `move` para o lugar inicial e narre o que o "
                "personagem percebe **neste** espaço.\n\n"
            )
    else:
        if intro_shown:
            second_reply = (
                f"**Não** repita esse texto na **segunda** mensagem (a que responde à ficha oculta {ref}). "
                "Narre o que o personagem percebe **neste** espaço a partir da "
                "intro e do system prompt; a tool **`move`** não está disponível — **não** a invoques. "
                "Sem reencenar a escalada da janela salvo **no máximo** uma frase de transição.\n\n"
            )
        else:
            second_reply = (
                f"**Não** repita esse texto na íntegra na **primeira** mensagem gerada para a UI (a que responde à "
                f"ficha oculta {ref}). Narre o que o personagem percebe **neste** espaço a partir do system prompt; "
                "a tool **`move`** não está disponível — **não** a invoques.\n\n"
            )
    heading = (
        "## Intro fixa (já exibida ao jogador, texto literal)\n\n"
        if intro_shown
        else "## Intro fixa (texto do mapa; contexto no prompt)\n\n"
    )
    ui_line = (
        "A interface enviou o bloco acima como **primeira** mensagem da narradora, **sem alterações**. "
        if intro_shown
        else "Este bloco **não** foi enviado como bolha separada na interface; consta **só** aqui como contexto. "
    )
    return f"{heading}{fixed}\n\n{ui_line}{second_reply}"


def secret_reveal_hard_rule() -> str:
    return (
        "SEGREDOS: nunca revele segredos, ocultos ou mistérios por padrão. "
        "Só revele se o jogador interagir exatamente do jeito certo com o elemento, "
        "ou se ele declarar investigação/percepção e obtiver sucesso em `roll_dice`. "
        "Aplique POV físico estrito: narre somente o que alguém naquele ponto da cena realmente "
        "percebe sem metaconhecimento do mapa."
    )


def opening_contract_for_narrator(app_config: AppConfig) -> str:
    ref = narrator_opening_turn_reference(app_config)
    intro_shown = fixed_intro_ui_enabled(app_config)
    parts = ["O arquivo de mapa do jogo é **%s**." % game_map_basename()]
    if app_config.include_tools_move:
        if intro_shown:
            parts.append(
                (
                    "A **segunda** mensagem do assistente na UI (após a intro fixa) deve **só** "
                    f"tratar da abertura inicial conforme {ref}: chame `move` para o lugar inicial "
                    f"**{STARTING_PLACE_NAME}** nesta jogada inicial e narre "
                    "a partir desse retorno. O texto da **`fixed_intro`** (se existir) está no system prompt **só** "
                    "como contexto: o jogador já leu tudo; **não** volte a colá-lo nem parafrasear por extenso."
                )
            )
        else:
            parts.append(
                (
                    "A **primeira** mensagem do assistente na UI deve **só** tratar da abertura inicial conforme "
                    f"{ref}: chame `move` para o lugar inicial **{STARTING_PLACE_NAME}** nesta jogada inicial e narre "
                    "a partir desse retorno. Se existir **`fixed_intro`** no mapa, funde o necessário na prosa sem "
                    "colar o parágrafo inteiro nem assumir que o jogador já viu esse texto na interface."
                )
            )
    else:
        if intro_shown:
            parts.append(
                (
                    "A **segunda** mensagem do assistente na UI (após a intro fixa) deve **só** "
                    f"tratar da abertura inicial conforme {ref} **sem** usar a tool **`move`** (indisponível). "
                    f"Ancore a narração no lugar inicial canônico (**{STARTING_PLACE_NAME}**) de forma coerente "
                    "com o mapa e com a **`fixed_intro`** no "
                    "system prompt — só como contexto: o jogador já leu tudo; **não** volte a colá-lo nem "
                    "parafrasear por extenso."
                )
            )
        else:
            parts.append(
                (
                    "A **primeira** mensagem do assistente na UI deve **só** tratar da abertura inicial conforme "
                    f"{ref} **sem** usar a tool **`move`** (indisponível). Ancore a narração no lugar inicial "
                    f"canônico (**{STARTING_PLACE_NAME}**) de forma coerente com o mapa. Se existir **`fixed_intro`** "
                    "no mapa, funde o necessário na prosa sem colar o parágrafo inteiro nem assumir que o jogador já "
                    "viu esse texto na interface."
                )
            )
    note = get_narrator_opening_note()
    if note:
        parts.append(note)
    return " ".join(parts)


def player_narrative_filters_section() -> str:
    filters = get_player_narrative_filters()
    if not filters:
        return ""
    lines = "\n".join(f"- {text}" for text in filters)
    return (
        "## Filtros de narração do personagem (mapa; obrigatório)\n\n"
        f"As linhas abaixo vêm do ficheiro **{game_map_basename()}** e **vinculam cada resposta**: "
        "integra-as na prosa em **segunda pessoa**, sem avisar o jogador que são «regras» ou "
        "«filtros».\n\n"
        f"{lines}\n\n"
        "Se uma linha **proíbe revelar informação escrita**, não narres leitura decifrada de "
        "documentos, placas, receitas ou inscrições no POV dele (podes notar traços, manchas ou "
        "forma, sem conteúdo literal salvo outro personagem ler em voz alta na cena). Evite também "
        "metalinguagem de alfabetização na prosa (ex.: «nada escrito chama sua atenção», «você não "
        "consegue ler isso»); prefira descrição física e sensorial (papel manchado, marcas de tinta, "
        "linhas indecifráveis, símbolo sem sentido para você). Se uma linha "
        "**exige teste de resistência** antes de um desfecho (ceder ou resistir a um impulso), "
        "**chama `roll_dice`** com dificuldade honesta **antes** de narrar o resultado. Se o "
        "desfecho for **ceder** a comida em excesso, narra também o **custo corporal** (fadiga leve a "
        "moderada na sensação, não no número) de forma natural nas respostas seguintes, alinhada ao "
        "**ENGINE_CONTEXT**.\n\n"
    )
