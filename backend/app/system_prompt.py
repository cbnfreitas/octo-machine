from app.messaging import build_turn_user_content
from app.config import AppConfig, get_app_config
from app.narrator_prompt import build_rpg_sections
from app.narrator_prompt.closing_reminder import final_checklist_reminder_section
from app.session_state import GameSessionState
from tools.move import (
    get_game_fixed_intro,
    get_opening_turn_player_intent_text,
    get_starting_place_name,
    has_spatial_map,
    move_to_place,
)

OPENING_USER_PLACEHOLDER = "(Sessão iniciada. A abertura já foi narrada ao jogador.)"


def fallback_opening_message(*, session_state: GameSessionState | None = None) -> str:
    """Last-resort second opening bubble if the model fails (fixed_intro is already on screen)."""
    fixed = get_game_fixed_intro()
    if has_spatial_map():
        start = get_starting_place_name()
        if start:
            try:
                block = move_to_place(start, session_state=session_state)
                summary = str(block["player_facing_summary"])
                if fixed.strip():
                    return summary
                return (
                    "Este é um RPG em texto: você explora **esta casa**, indo de um lugar a outro.\n\n"
                    f"{summary}"
                )
            except Exception:
                pass
    if fixed.strip():
        return (
            f"{fixed.strip()}\n\n"
            "Você hesita no mesmo instante; o ar parece aguardar a sua próxima escolha."
        )
    return "Algo pressiona a cena para frente; o que você faz?"


def opening_turn_user_content(
    *,
    fatigue_percent: float = 0.0,
    game_clock_minutes: float = 0.0,
    app_config: AppConfig | None = None,
) -> str:
    cfg = app_config or get_app_config()
    return build_turn_user_content(
        get_opening_turn_player_intent_text(cfg),
        fatigue_percent=fatigue_percent,
        game_clock_minutes=game_clock_minutes,
        current_place_name=None,
        known_place_names=(),
        stash_items=(),
    )


def chat_system_content(*, app_config: AppConfig | None = None) -> str:
    cfg = app_config or get_app_config()
    body = build_rpg_sections(cfg)
    if cfg.include_final_checklist_reminder:
        return f"{body}\n\n{final_checklist_reminder_section()}"
    return body
