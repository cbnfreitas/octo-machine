"""
Compose LLM-facing user turns: parallel Player intent + Engine context (sync), per diagram.
"""

from __future__ import annotations

from app.game_clock import format_game_clock_for_prompt
from app.internal_acrobatics import fatigue_label_for_context
from app.participants import Participant

# Headers tie each block to a diagram participant; content is Portuguese for the narrator LLM.
SECTION_PLAYER_INTENT = f"### PLAYER_INTENT ({Participant.PLAYER.value} → narrador)"
SECTION_ENGINE_CONTEXT = f"### ENGINE_CONTEXT ({Participant.ENGINE_TOOLS.value} → narrador, sync)"


def format_engine_context_for_prompt(
    *,
    fatigue_percent: float,
    game_clock_minutes: float,
    current_place_name: str | None = None,
    known_place_names: tuple[str, ...] | None = None,
    stash_items: tuple[str, ...] | None = None,
) -> str:
    label = fatigue_label_for_context(fatigue_percent)
    clock = format_game_clock_for_prompt(game_clock_minutes)
    pos = (
        current_place_name.strip()
        if isinstance(current_place_name, str) and current_place_name.strip()
        else "(ainda não posicionado pelo motor)"
    )
    if known_place_names:
        known_line = ", ".join(known_place_names)
    else:
        known_line = "(nenhum ainda)"
    if stash_items:
        stash_line = ", ".join(stash_items)
    else:
        stash_line = "(vazio)"
    return (
        f"{SECTION_ENGINE_CONTEXT}\n"
        "- Fadiga interna (acrobacia), só qualitativa: "
        f"{label} "
        "(sem números; não é dado que o personagem leia como estatística.)\n"
        "- Tempo in-game (estimativa do motor), relógio 24h: "
        f"**{clock}** — âncora para passagem de tempo na ficção; não exponha como interface nem "
        "leia o horário em voz alta de forma meta, salvo se a cena tiver um relógio ou alguém "
        "perguntar as horas.\n"
        f"- **Lugar atual (nome canônico do mapa):** {pos}\n"
        "- **Nomes do mapa que o jogador já visitou** (pode tratar como «já vi este cômodo»; "
        "intenção em **primeira pessoa** não deve nomear destinos **fora** desta lista como fato "
        f"que o personagem já conhece): {known_line}\n"
        f"- **Itens no saco (stash) do jogador:** {stash_line}"
    )


def build_turn_user_content(
    player_intent: str,
    *,
    fatigue_percent: float,
    game_clock_minutes: float,
    current_place_name: str | None = None,
    known_place_names: tuple[str, ...] | None = None,
    stash_items: tuple[str, ...] | None = None,
) -> str:
    intent = player_intent.strip()
    ctx = format_engine_context_for_prompt(
        fatigue_percent=fatigue_percent,
        game_clock_minutes=game_clock_minutes,
        current_place_name=current_place_name,
        known_place_names=known_place_names,
        stash_items=stash_items,
    )
    return f"{SECTION_PLAYER_INTENT}\n{intent}\n\n{ctx}"
