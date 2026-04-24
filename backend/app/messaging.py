"""
Compose LLM-facing user turns: parallel Player intent + Engine context (sync), per diagram.
"""

from __future__ import annotations

from app.internal_acrobatics import fatigue_label_for_context
from app.participants import Participant

# Headers tie each block to a diagram participant; content is Portuguese for the narrator LLM.
SECTION_PLAYER_INTENT = f"### PLAYER_INTENT ({Participant.PLAYER.value} → narrador)"
SECTION_ENGINE_CONTEXT = f"### ENGINE_CONTEXT ({Participant.ENGINE_TOOLS.value} → narrador, sync)"


def format_engine_context_for_prompt(fatigue_percent: float) -> str:
    label = fatigue_label_for_context(fatigue_percent)
    return (
        f"{SECTION_ENGINE_CONTEXT}\n"
        "- Fadiga interna (acrobacia), só qualitativa: "
        f"{label} "
        "(sem números; não é dado que o personagem leia como estatística.)"
    )


def build_turn_user_content(player_intent: str, *, fatigue_percent: float) -> str:
    intent = player_intent.strip()
    ctx = format_engine_context_for_prompt(fatigue_percent)
    return f"{SECTION_PLAYER_INTENT}\n{intent}\n\n{ctx}"
