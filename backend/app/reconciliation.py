"""
Reconciliation LLM: reads the turn and updates engine state via tools (e.g. acrobatics fatigue).
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam

from app.internal_acrobatics import fatigue_label_for_context
from app.logging_config import logger
from app.participants import AsyncChannel
from app.reconciliation_prompt import reconciliation_system_prompt
from app.session_state import GameSessionState

_RECONCILIATION_MODEL = os.getenv("RECONCILIATION_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
_MAX_DELTA_PER_TURN = 50.0
_MAX_TOOL_ATTEMPTS = 3

ADJUST_FATIGUE_TOOL_NAME = "adjust_acrobatics_fatigue"

RECONCILIATION_TOOLS: list[ChatCompletionToolUnionParam] = cast(
    list[ChatCompletionToolUnionParam],
    [
    {
        "type": "function",
        "function": {
            "name": ADJUST_FATIGUE_TOOL_NAME,
            "description": (
                "Aplica mudança aditiva à fadiga interna (acrobacia), 0–100 no motor. "
                "Negativo recupera; positivo acumula cansaço. O motor faz clamp final."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "delta": {
                        "type": "number",
                        "description": (
                            "Pontos a somar à fadiga (ex.: -15 após descanso, +8 após esforço). "
                            "Use 0 se o turno não alterar o cansaço."
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": "Justificativa curta para log técnico (PT-BR).",
                    },
                },
                "required": ["delta", "reason"],
            },
        },
    }
    ],
)


@dataclass(frozen=True)
class ReconciliationTurnSnapshot:
    player_intent_plain: str
    narration_to_player: str
    tool_result_contents: list[str]
    hidden_beyond_player_perception: str = ""


def _build_reconciliation_user_content(snap: ReconciliationTurnSnapshot, fatigue_before: float) -> str:
    label = fatigue_label_for_context(fatigue_before)
    tools_block = (
        "\n---\n".join(snap.tool_result_contents) if snap.tool_result_contents else "(nenhum resultado de tool neste turno)"
    )
    hidden = snap.hidden_beyond_player_perception.strip() or "(nada fornecido)"
    return (
        "### Estado atual (fadiga interna - acrobacia)\n"
        f"Valor motor: {fatigue_before:.1f}/100. Rótulo qualitativo: {label}\n\n"
        "### Intenção do jogador (referência; não basta para gastar energia sem narração)\n"
        f"{snap.player_intent_plain}\n\n"
        "### Narração mostrada ao jogador (o que conta para desfecho físico neste turno)\n"
        f"{snap.narration_to_player}\n\n"
        "### Resultados das ferramentas (JSON)\n"
        f"{tools_block}\n\n"
        "### Informação além da percepção do jogador\n"
        f"{hidden}\n\n"
        "Chame **adjust_acrobatics_fatigue**. Se a narração não consolidou esforço, falha, manobra ou "
        "descanso **na ficção**, e não há `action_outcome` (ou outro sinal físico) nos JSONs, use "
        "**delta 0**."
    )


def _clamp_delta(raw: float) -> tuple[float, bool]:
    clamped = max(-_MAX_DELTA_PER_TURN, min(_MAX_DELTA_PER_TURN, raw))
    return clamped, clamped != raw


def _parse_adjust_call(arguments_json: str) -> tuple[float, str]:
    raw = json.loads(arguments_json) if arguments_json else {}
    if not isinstance(raw, dict):
        raise ValueError("tool arguments must be an object")
    delta_val = raw.get("delta")
    if not isinstance(delta_val, (int, float)):
        raise ValueError("delta must be a number")
    delta = float(delta_val)
    reason = raw.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)
    return delta, reason.strip()


async def apply_reconciliation_llm(client: OpenAI, state: GameSessionState, snap: ReconciliationTurnSnapshot) -> None:
    async with state.lock:
        fatigue_before = state.fatigue_percent

    user_content = _build_reconciliation_user_content(snap, fatigue_before)
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": reconciliation_system_prompt()},
        {"role": "user", "content": user_content},
    ]

    logger.info(
        "[%s] model=%s fatigue_before=%.1f intent_preview=%r",
        "reconciliation_llm",
        _RECONCILIATION_MODEL,
        fatigue_before,
        (snap.player_intent_plain[:100] + "…") if len(snap.player_intent_plain) > 100 else snap.player_intent_plain,
    )

    tool_calls_executed = 0
    for attempt in range(_MAX_TOOL_ATTEMPTS):
        def _create() -> Any:
            return client.chat.completions.create(
                model=_RECONCILIATION_MODEL,
                messages=messages,
                tools=RECONCILIATION_TOOLS,
                tool_choice={
                    "type": "function",
                    "function": {"name": ADJUST_FATIGUE_TOOL_NAME},
                },
            )

        response = await asyncio.to_thread(_create)
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.function.name != ADJUST_FATIGUE_TOOL_NAME:
                    logger.warning("[%s] ignored tool %s", "reconciliation_llm", tc.function.name)
                    continue
                try:
                    raw_delta, reason = _parse_adjust_call(str(tc.function.arguments or ""))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("[%s] bad tool arguments: %s", "reconciliation_llm", e)
                    continue
                delta, was_clamped = _clamp_delta(raw_delta)
                async with state.lock:
                    before = state.fatigue_percent
                    state.fatigue_percent = min(100.0, max(0.0, before + delta))
                    after = state.fatigue_percent
                tool_calls_executed += 1
                logger.info(
                    "[%s] %s fatigue %.1f -> %.1f (delta %+.1f%s) reason=%r",
                    "reconciliation_llm",
                    AsyncChannel.RECONCILIATION_CONTEXT_UPDATE_TO_ENGINE.value,
                    before,
                    after,
                    delta,
                    " CLAMPED" if was_clamped else "",
                    reason[:200],
                )
                break
            break

        messages.append({"role": "assistant", "content": msg.content or ""})
        messages.append(
            {
                "role": "user",
                "content": "Você precisa chamar a ferramenta adjust_acrobatics_fatigue (delta numérico e reason).",
            }
        )

    if tool_calls_executed == 0:
        logger.error("[%s] no valid tool call after %s attempts", "reconciliation_llm", _MAX_TOOL_ATTEMPTS)
