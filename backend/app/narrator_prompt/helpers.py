from app.config import AppConfig

from tools.move import (
    fixed_intro_ui_enabled,
    game_map_basename,
    get_narrator_opening_note,
    get_player_narrative_filters,
    get_starting_place_name,
    has_spatial_map,
    narrator_opening_turn_reference,
)


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
    start = get_starting_place_name()
    parts = ["O arquivo de mapa do jogo é **%s**." % game_map_basename()]
    if app_config.include_tools_move:
        label = start or "(defina starting_place_name ou um mapa espacial no JSON)"
        if intro_shown:
            parts.append(
                (
                    "A **segunda** mensagem do assistente na UI (após a intro fixa) deve **só** "
                    f"tratar da abertura inicial conforme {ref}: chame `move` para o lugar inicial "
                    f"**{label}** nesta jogada inicial e narre "
                    "a partir desse retorno. O texto da **`fixed_intro`** (se existir) está no system prompt **só** "
                    "como contexto: o jogador já leu tudo; **não** volte a colá-lo nem parafrasear por extenso."
                )
            )
        else:
            parts.append(
                (
                    "A **primeira** mensagem do assistente na UI deve **só** tratar da abertura inicial conforme "
                    f"{ref}: chame `move` para o lugar inicial **{label}** nesta jogada inicial e narre "
                    "a partir desse retorno. Se existir **`fixed_intro`** no mapa, funde o necessário na prosa sem "
                    "colar o parágrafo inteiro nem assumir que o jogador já viu esse texto na interface."
                )
            )
    else:
        if has_spatial_map() and start:
            place_phrase = f"no lugar inicial canônico do mapa (**{start}**)"
        elif has_spatial_map():
            place_phrase = "no estado inicial coerente com o mapa"
        else:
            place_phrase = (
                "no espaço inicial descrito na **`fixed_intro`** e no **main_plot**, sem inventar cômodos que "
                "não constem desse material"
            )
        if intro_shown:
            parts.append(
                (
                    "A **segunda** mensagem do assistente na UI (após a intro fixa) deve **só** "
                    f"tratar da abertura inicial conforme {ref} **sem** usar a tool **`move`** (indisponível). "
                    f"Ancore a narração {place_phrase} e com a **`fixed_intro`** no "
                    "system prompt — só como contexto: o jogador já leu tudo; **não** volte a colá-lo nem "
                    "parafrasear por extenso."
                )
            )
        else:
            parts.append(
                (
                    "A **primeira** mensagem do assistente na UI deve **só** tratar da abertura inicial conforme "
                    f"{ref} **sem** usar a tool **`move`** (indisponível). Ancore a narração {place_phrase}. "
                    "Se existir **`fixed_intro`** "
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
