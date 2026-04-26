from app.messaging import build_turn_user_content
from app.config import AppConfig, get_app_config
from app.narrator_prompt import build_rpg_sections
from app.narrator_prompt.closing_reminder import final_checklist_reminder_section
from app.session_state import GameSessionState
from tools import combined_tool_instructions
from tools.move import (
    STARTING_PLACE_NAME,
    get_game_fixed_intro,
    get_narrator_opening_note,
    get_opening_turn_player_intent_text,
    move_to_place,
    narrator_opening_turn_reference,
)

OPENING_USER_PLACEHOLDER = "(Sessão iniciada. A abertura já foi narrada ao jogador.)"


def fallback_opening_message(*, session_state: GameSessionState | None = None) -> str:
    """Last-resort second opening bubble if the model fails (fixed_intro is already on screen)."""
    fixed = get_game_fixed_intro()
    start = move_to_place(STARTING_PLACE_NAME, session_state=session_state)
    summary = str(start["player_facing_summary"])
    if fixed.strip():
        return summary
    return (
        "Este é um RPG em texto: você explora **esta casa**, indo de um lugar a outro.\n\n"
        f"{summary}"
    )


def opening_turn_user_content(
    *,
    fatigue_percent: float = 0.0,
    game_clock_minutes: float = 0.0,
    app_config: AppConfig | None = None,
) -> str:
    cfg = app_config or get_app_config()
    note_block = ""
    n = get_narrator_opening_note()
    if n.strip():
        note_block = f"\n### Nota do mapa para a abertura (respeita)\n{n.strip()}\n"
    turn = build_turn_user_content(
        get_opening_turn_player_intent_text(cfg),
        fatigue_percent=fatigue_percent,
        game_clock_minutes=game_clock_minutes,
        current_place_name=None,
        known_place_names=(),
        stash_items=(),
    )
    if cfg.include_opening_player_line:
        answer_clause = (
            f"Responda de forma coerente à fala simulada do jogador {narrator_opening_turn_reference(cfg)} "
            "em **uma única** mensagem, em PT-BR, obedecendo POV, segredo e "
            "economia de detalhe do system prompt. **Não duplique** parágrafos. Se a intro fixa já cobriu faca, "
            "aldrava e entrada pela janela, **não** recomece essa sequência: faça só uma transição curta em prosa "
            "natural e siga para o que ele nota **neste** cômodo. **Nunca** exponha instruções internas em voz de "
            "narrador (evite frases metalinguísticas como \"uma frase para ligar...\").\n\n"
        )
    else:
        answer_clause = (
            "Em **uma única** mensagem, em PT-BR, narre onde o personagem está **agora** após a intro fixa, "
            "obedecendo POV, segredo e economia de detalhe do system prompt. **Não duplique** parágrafos. "
            "Se a intro fixa já cobriu faca, aldrava e entrada pela janela, **não** recomece essa sequência: "
            "faça só uma transição curta em prosa natural e siga para o que ele nota **neste** cômodo. "
            "**Nunca** exponha instruções internas em voz de narrador (evite frases metalinguísticas como "
            "\"uma frase para ligar...\").\n\n"
        )
    if cfg.include_tools_move:
        place_step = (
            f"Antes de narrar onde o personagem está **agora**, chame `move` para o lugar inicial "
            f"**{STARTING_PLACE_NAME}** e use o resultado como base factual da cena. "
        )
    else:
        place_step = (
            "Narra onde o personagem está **agora** com base na **intro fixa** (se existir) e no system "
            "prompt. A tool **`move`** não está disponível nesta configuração: **não** a invoques. Ancore a "
            "cena no estado inicial coerente com o mapa (lugar inicial canônico: "
            f"**{STARTING_PLACE_NAME}**), sem inventar fatos nem contradizer o texto de apoio. "
        )
    return (
        f"{turn}\n\n"
        "### Instrução (início de sessão)\n\n"
        "Esta é a primeira jogada real da sessão. A **intro fixa** do mapa já foi mostrada ao jogador "
        "(texto literal pela interface) e está no system prompt; **não** a repita. "
        f"{place_step}"
        f"{answer_clause}"
        f"{note_block}"
    )


def chat_system_content(*, app_config: AppConfig | None = None) -> str:
    cfg = app_config or get_app_config()
    body = build_rpg_sections(cfg)
    tools = combined_tool_instructions(cfg)
    if tools.strip():
        head = f"{body}\n\n## Referência das ferramentas\n\n{tools}"
    else:
        head = body
    if cfg.include_final_checklist_reminder:
        return f"{head}\n\n{final_checklist_reminder_section()}"
    return head
