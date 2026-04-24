"""
Identifiers for the message flow: Player, Narrator (LLM), Engine tools, Reconciliation (LLM).
See diagrama_troca_mensagens.md.
"""

from __future__ import annotations

from enum import StrEnum


class Participant(StrEnum):
    PLAYER = "player"
    NARRATOR_LLM = "narrator_llm"
    ENGINE_TOOLS = "engine_tools"
    RECONCILIATION_LLM = "reconciliation_llm"


class SyncChannel(StrEnum):
    """Synchronous edges in the sequence diagram."""

    PLAYER_INTENT_TO_NARRATOR = "player_intent_to_narrator"
    ENGINE_CONTEXT_TO_NARRATOR = "engine_context_to_narrator"
    NARRATOR_TOOL_CALL_TO_ENGINE = "narrator_tool_call_to_engine"
    ENGINE_TOOL_RESULT_TO_NARRATOR = "engine_tool_result_to_narrator"
    NARRATOR_NARRATION_TO_PLAYER = "narrator_narration_to_player"


class AsyncChannel(StrEnum):
    """Asynchronous edges (reconciliation path)."""

    NARRATOR_NARRATION_TO_RECONCILIATION = "narrator_narration_to_reconciliation"
    NARRATOR_HIDDEN_TO_RECONCILIATION = "narrator_hidden_to_reconciliation"
    RECONCILIATION_CONTEXT_UPDATE_TO_ENGINE = "reconciliation_context_update_to_engine"
