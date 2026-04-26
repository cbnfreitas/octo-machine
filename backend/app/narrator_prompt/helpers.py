from tools.move import (
    GAME_MAP_BASENAME,
    STARTING_PLACE_NAME,
    get_game_fixed_intro,
    get_narrator_opening_note,
    get_player_narrative_filters,
)


def fixed_intro_context_section() -> str:
    fixed = get_game_fixed_intro().strip()
    if not fixed:
        return ""
    return (
        "## Intro fixa (já exibida ao jogador, texto literal)\n\n"
        f"{fixed}\n\n"
        "A interface enviou o bloco acima como **primeira** mensagem da narradora, **sem alterações**. "
        "**Não** repita esse texto na **segunda** mensagem (a que responde à ficha oculta "
        "«Vamos começar, onde estou?»). Nessa resposta use só `move` para o lugar inicial e narre o que o "
        "personagem percebe **neste** espaço, sem reencenar a escalada da janela salvo **no máximo** uma "
        "frase de transição.\n\n"
    )


def secret_reveal_hard_rule() -> str:
    return (
        "SEGREDOS: nunca revele segredos, ocultos ou mistérios por padrão. "
        "Só revele se o jogador interagir exatamente do jeito certo com o elemento, "
        "ou se ele declarar investigação/percepção e obtiver sucesso em `roll_dice`. "
        "Aplique POV físico estrito: narre somente o que alguém naquele ponto da cena realmente "
        "percebe sem metaconhecimento do mapa."
    )


def opening_contract_for_narrator() -> str:
    parts = [
        "O arquivo de mapa do jogo é **%s**." % GAME_MAP_BASENAME,
        (
            "A **segunda** mensagem do assistente na UI (após a intro fixa, se houver) deve **só** "
            "responder «onde estou?»: chame `move` para o lugar inicial **%s** nesta jogada inicial e narre "
            "a partir desse retorno. O texto da **`fixed_intro`** (se existir) está no system prompt **só** "
            "como contexto: o jogador já leu tudo; **não** volte a colá-lo nem parafrasear por extenso."
            % STARTING_PLACE_NAME
        ),
    ]
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
        f"As linhas abaixo vêm do ficheiro **{GAME_MAP_BASENAME}** e **vinculam cada resposta**: "
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
