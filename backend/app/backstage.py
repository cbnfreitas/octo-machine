"""
Backstage LLM: reads the turn and updates engine state via tools (e.g. acrobatics fatigue, game clock).
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam

from app.backstage_prompt import backstage_system_prompt
from app.game_clock import format_game_clock_for_prompt, normalize_clock_minutes
from app.internal_acrobatics import fatigue_label_for_context
from app.logging_config import logger
from app.participants import AsyncChannel
from app.session_state import GameSessionState


def _hhmm() -> str:
    return datetime.now().strftime("%H:%M")


_BACKSTAGE_MODEL = os.getenv("BACKSTAGE_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
_MAX_FATIGUE_DELTA_PER_TURN = 50.0
_MAX_GAME_TIME_DELTA_PER_TURN = 240.0
_MAX_TOOL_ATTEMPTS = 3

ADJUST_BACKSTAGE_TOOL_NAME = "adjust_backstage_state"
ADJUST_WORLD_TOOL_NAME = "adjust_world_state"

BACKSTAGE_TOOLS: list[ChatCompletionToolUnionParam] = cast(
    list[ChatCompletionToolUnionParam],
    [
        {
            "type": "function",
            "function": {
                "name": ADJUST_BACKSTAGE_TOOL_NAME,
                "description": (
                    "Atualiza fadiga interna (acrobacia) e o relógio in-game do turno. O motor aplica "
                    "clamp de fadiga 0–100 e ciclo de 24h no relógio. Use deltas 0 quando o turno não "
                    "justificar mudança."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fatigue_delta": {
                            "type": "number",
                            "description": (
                                "Pontos a somar à fadiga 0–100 (negativo recupera). 0 se não houver "
                                "novo esforço ou recuperação na ficção."
                            ),
                        },
                        "game_time_delta_minutes": {
                            "type": "number",
                            "description": (
                                "Minutos in-game a somar ao relógio (pode ser fracionário; ex.: 2 após "
                                "diálogo curto, 15 após sequência física). 0 se a cena for instantânea."
                            ),
                        },
                        "reason": {
                            "type": "string",
                            "description": "Justificativa curta para log técnico (PT-BR), cobrindo fadiga e tempo.",
                        },
                    },
                    "required": ["fatigue_delta", "game_time_delta_minutes", "reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": ADJUST_WORLD_TOOL_NAME,
                "description": (
                    "Atualiza estado do mundo após ações já concretizadas na narração: stash do jogador "
                    "e termos que devem sumir da descrição de um lugar."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stash_add": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Itens para adicionar ao saco do jogador neste turno.",
                        },
                        "place_description_removals": {
                            "type": "array",
                            "description": (
                                "Lista de ajustes visuais por lugar, removendo termos da descrição base."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "place_name": {"type": "string"},
                                    "terms": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["place_name", "terms"],
                            },
                        },
                        "reason": {
                            "type": "string",
                            "description": "Justificativa curta para log técnico (PT-BR).",
                        },
                    },
                    "required": ["stash_add", "place_description_removals", "reason"],
                },
            },
        },
    ],
)


@dataclass(frozen=True)
class BackstageTurnSnapshot:
    player_intent_plain: str
    narration_to_player: str
    tool_result_contents: list[str]
    hidden_beyond_player_perception: str = ""


def _build_backstage_user_content(
    snap: BackstageTurnSnapshot,
    fatigue_before: float,
    game_clock_before: float,
    stash_before: tuple[str, ...],
    removed_terms_before: dict[str, tuple[str, ...]],
) -> str:
    label = fatigue_label_for_context(fatigue_before)
    clock = format_game_clock_for_prompt(game_clock_before)
    tools_block = (
        "\n---\n".join(snap.tool_result_contents) if snap.tool_result_contents else "(nenhum resultado de tool neste turno)"
    )
    hidden = snap.hidden_beyond_player_perception.strip() or "(nada fornecido)"
    stash_line = ", ".join(stash_before) if stash_before else "(vazio)"
    if removed_terms_before:
        removed_lines = []
        for place_name in sorted(removed_terms_before):
            terms = ", ".join(removed_terms_before[place_name])
            removed_lines.append(f"- {place_name}: {terms}")
        removed_block = "\n".join(removed_lines)
    else:
        removed_block = "(nenhum termo removido)"
    return (
        "### Estado atual (fadiga interna - acrobacia)\n"
        f"Valor motor: {fatigue_before:.1f}/100. Rótulo qualitativo: {label}\n\n"
        "### Estado atual (relógio in-game, minutos desde meia-noite, ciclo 24h)\n"
        f"Relógio motor: {game_clock_before:.2f} min (≈ {clock})\n\n"
        "### Intenção do jogador (referência; não basta para gastar energia ou tempo sem narração)\n"
        f"{snap.player_intent_plain}\n\n"
        "### Narração mostrada ao jogador (o que conta para desfecho físico e passagem de tempo neste turno)\n"
        f"{snap.narration_to_player}\n\n"
        "### Resultados das ferramentas (JSON)\n"
        f"{tools_block}\n\n"
        "### Informação além da percepção do jogador\n"
        f"{hidden}\n\n"
        "### Estado do mundo atual (persistente)\n"
        f"- Itens no saco (stash): {stash_line}\n"
        f"- Termos removidos das descrições por lugar:\n{removed_block}\n\n"
        "Chame **adjust_backstage_state** com **fatigue_delta** e **game_time_delta_minutes**. Se a narração "
        "não consolidou esforço, falha, manobra ou descanso **na ficção**, e não há sinal físico nos JSONs, "
        "use **fatigue_delta 0**. Se o turno for só troca de frases, esclarecimento ou foco no mesmo instante, "
        "use **game_time_delta_minutes 0** (ou poucos minutos se a prosa indicar pausa curta real).\n\n"
        "Quando houver mudança concreta de objetos no mundo (item pego, roubado, quebrado, consumido, "
        "sumido da cena), chame também **adjust_world_state** no mesmo turno para manter consistência: "
        "adicione item em `stash_add` e remova termos da descrição em `place_description_removals`."
    )


def _clamp_fatigue_delta(raw: float) -> tuple[float, bool]:
    clamped = max(-_MAX_FATIGUE_DELTA_PER_TURN, min(_MAX_FATIGUE_DELTA_PER_TURN, raw))
    return clamped, clamped != raw


def _clamp_time_delta(raw: float) -> tuple[float, bool]:
    clamped = max(-_MAX_GAME_TIME_DELTA_PER_TURN, min(_MAX_GAME_TIME_DELTA_PER_TURN, raw))
    return clamped, clamped != raw


def _parse_backstage_adjust(arguments_json: str) -> tuple[float, float, str]:
    raw = json.loads(arguments_json) if arguments_json else {}
    if not isinstance(raw, dict):
        raise ValueError("tool arguments must be an object")
    fd = raw.get("fatigue_delta")
    if not isinstance(fd, (int, float)):
        raise ValueError("fatigue_delta must be a number")
    td = raw.get("game_time_delta_minutes")
    if not isinstance(td, (int, float)):
        raise ValueError("game_time_delta_minutes must be a number")
    reason = raw.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)
    return float(fd), float(td), reason.strip()


def _parse_world_adjust(arguments_json: str) -> tuple[list[str], list[tuple[str, list[str]]], str]:
    raw = json.loads(arguments_json) if arguments_json else {}
    if not isinstance(raw, dict):
        raise ValueError("tool arguments must be an object")
    stash_raw = raw.get("stash_add", [])
    if not isinstance(stash_raw, list):
        raise ValueError("stash_add must be an array")
    stash_add = [str(item).strip() for item in stash_raw if str(item).strip()]

    removals_raw = raw.get("place_description_removals", [])
    if not isinstance(removals_raw, list):
        raise ValueError("place_description_removals must be an array")
    removals: list[tuple[str, list[str]]] = []
    for item in removals_raw:
        if not isinstance(item, dict):
            continue
        place_name = str(item.get("place_name", "")).strip()
        terms_raw = item.get("terms", [])
        if not place_name or not isinstance(terms_raw, list):
            continue
        terms = [str(term).strip() for term in terms_raw if str(term).strip()]
        if terms:
            removals.append((place_name, terms))

    reason = raw.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)
    return stash_add, removals, reason.strip()


async def apply_backstage_llm(client: OpenAI, state: GameSessionState, snap: BackstageTurnSnapshot) -> None:
    async with state.lock:
        fatigue_before = state.fatigue_percent
        game_clock_before = state.game_clock_minutes
        stash_before = tuple(sorted(state.stash_items))
        removed_terms_before = {
            place_name: tuple(sorted(terms))
            for place_name, terms in state.place_description_removed_terms.items()
        }

    user_content = _build_backstage_user_content(
        snap,
        fatigue_before,
        game_clock_before,
        stash_before,
        removed_terms_before,
    )
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": backstage_system_prompt()},
        {"role": "user", "content": user_content},
    ]

    logger.info(
        "[%s] [backstage_llm] model=%s fatigue_before=%.1f clock_before=%s intent_preview=%r",
        _hhmm(),
        _BACKSTAGE_MODEL,
        fatigue_before,
        format_game_clock_for_prompt(game_clock_before),
        (snap.player_intent_plain[:100] + "…") if len(snap.player_intent_plain) > 100 else snap.player_intent_plain,
    )

    tool_calls_executed = 0
    for _attempt in range(_MAX_TOOL_ATTEMPTS):
        def _create() -> Any:
            return client.chat.completions.create(
                model=_BACKSTAGE_MODEL,
                messages=messages,
                tools=BACKSTAGE_TOOLS,
            )

        response = await asyncio.to_thread(_create)
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.function.name == ADJUST_BACKSTAGE_TOOL_NAME:
                    try:
                        raw_f, raw_t, reason = _parse_backstage_adjust(str(tc.function.arguments or ""))
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning("[%s] [backstage_llm] bad tool arguments: %s", _hhmm(), e)
                        continue
                    fatigue_delta, f_clamped = _clamp_fatigue_delta(raw_f)
                    time_delta, t_clamped = _clamp_time_delta(raw_t)
                    async with state.lock:
                        fb = state.fatigue_percent
                        tb = state.game_clock_minutes
                        state.fatigue_percent = min(100.0, max(0.0, fb + fatigue_delta))
                        state.game_clock_minutes = normalize_clock_minutes(tb + time_delta)
                        fa = state.fatigue_percent
                        ta = state.game_clock_minutes
                    tool_calls_executed += 1
                    ch = AsyncChannel.BACKSTAGE_CONTEXT_UPDATE_TO_ENGINE.value
                    logger.info(
                        "[%s] [backstage_llm] %s fatigue %.1f -> %.1f (delta %+.1f%s) reason=%r",
                        _hhmm(),
                        ch,
                        fb,
                        fa,
                        fatigue_delta,
                        " CLAMPED" if f_clamped else "",
                        reason[:200],
                    )
                    logger.info(
                        "[%s] [backstage_llm] %s clock %s -> %s (delta %+.2f min%s) reason=%r",
                        _hhmm(),
                        ch,
                        format_game_clock_for_prompt(tb),
                        format_game_clock_for_prompt(ta),
                        time_delta,
                        " CLAMPED" if t_clamped else "",
                        reason[:200],
                    )
                    continue

                if tc.function.name == ADJUST_WORLD_TOOL_NAME:
                    try:
                        stash_add, removals, reason = _parse_world_adjust(str(tc.function.arguments or ""))
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning("[%s] [backstage_llm] bad world args: %s", _hhmm(), e)
                        continue
                    async with state.lock:
                        before_stash = len(state.stash_items)
                        state.stash_items.update(stash_add)
                        for place_name, terms in removals:
                            bucket = state.place_description_removed_terms.setdefault(place_name, set())
                            bucket.update(terms)
                        after_stash = len(state.stash_items)
                    tool_calls_executed += 1
                    logger.info(
                        "[%s] [backstage_llm] world stash +%d, places_changed=%d reason=%r",
                        _hhmm(),
                        after_stash - before_stash,
                        len(removals),
                        reason[:200],
                    )
                    continue

                logger.warning("[%s] [backstage_llm] ignored tool %s", _hhmm(), tc.function.name)
            break

        messages.append({"role": "assistant", "content": msg.content or ""})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Você precisa chamar adjust_backstage_state neste turno e pode chamar "
                    "adjust_world_state quando houver mudança concreta de objetos/cena."
                ),
            }
        )

    if tool_calls_executed == 0:
        logger.error(
            "[%s] [backstage_llm] no valid tool call after %s attempts",
            _hhmm(),
            _MAX_TOOL_ATTEMPTS,
        )
