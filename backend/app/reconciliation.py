"""
Reconciliation (LLM path placeholder): async context updates Engine state after narration.

Currently applies a small fatigue delta from action_outcome tool JSON in the finished turn.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.logging_config import logger
from app.participants import AsyncChannel
from app.session_state import GameSessionState


@dataclass(frozen=True)
class ReconciliationTurnSnapshot:
    """Payload matching AsyncChannel edges toward reconciliation + engine update."""

    narration_to_player: str
    tool_result_contents: list[str]
    # Reserved for NARRATOR_HIDDEN_TO_RECONCILIATION (beyond player perception); LLM hook later.
    hidden_beyond_player_perception: str = ""


_OUTCOME_FATIGUE_DELTA: dict[str, float] = {
    "sucesso_critico": 1.5,
    "sucesso": 3.0,
    "falha": 5.0,
    "falha_critica": 7.0,
}


def _fatigue_delta_from_action_outcome_json(content: str) -> float:
    try:
        obj = json.loads(content)
    except json.JSONDecodeError:
        return 0.0
    if not isinstance(obj, dict):
        return 0.0
    outcome = obj.get("outcome")
    if not isinstance(outcome, str):
        return 0.0
    return _OUTCOME_FATIGUE_DELTA.get(outcome, 0.0)


def compute_fatigue_delta_from_tool_results(tool_result_contents: list[str]) -> float:
    return sum(_fatigue_delta_from_action_outcome_json(c) for c in tool_result_contents)


async def apply_reconciliation_snapshot(
    state: GameSessionState,
    snap: ReconciliationTurnSnapshot,
) -> None:
    """
    Applies AsyncChannel.RECONCILIATION_CONTEXT_UPDATE_TO_ENGINE for fatigue (rule-based MVP).
    Later: optional second LLM with NARRATION + HIDDEN payloads.
    """
    delta = compute_fatigue_delta_from_tool_results(snap.tool_result_contents)
    if delta <= 0:
        return
    async with state.lock:
        before = state.fatigue_percent
        state.fatigue_percent = min(100.0, state.fatigue_percent + delta)
        after = state.fatigue_percent
    if delta > 0:
        logger.info(
            "[%s] fatigue %.1f -> %.1f (delta +%.1f from tool results)",
            AsyncChannel.RECONCILIATION_CONTEXT_UPDATE_TO_ENGINE.value,
            before,
            after,
            delta,
        )
