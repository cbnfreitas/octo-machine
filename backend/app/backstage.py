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


def _sanitize_model_text(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch != "\x00")
    return " ".join(cleaned.split())


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
                    "e camadas dinâmicas **description** e **details** por lugar."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stash_add": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Itens para adicionar ao saco do jogador neste turno.",
                        },
                        "place_description_updates": {
                            "type": "array",
                            "description": (
                                "Lista de camadas **basic_description** e **details** completas por lugar afetado "
                                "(texto integral de cada camada após a mudança; coerente com a narração)."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "place_name": {"type": "string"},
                                    "basic_description": {
                                        "type": "string",
                                        "description": (
                                            "Camada principal do lugar (impressão imediata ao chegar); "
                                            "PT-BR, texto completo atualizado."
                                        ),
                                    },
                                    "details": {
                                        "type": "string",
                                        "description": (
                                            "Camada secundária (textura extra, arrumação, micro-cena); "
                                            "PT-BR, texto completo atualizado. Use string vazia só se o mapa "
                                            "não tiver detalhes para esse lugar."
                                        ),
                                    },
                                },
                                "required": ["place_name", "basic_description", "details"],
                            },
                        },
                        "scene_facts": {
                            "type": "string",
                            "description": (
                                "Fichas de cena em PT-BR: 2 a 8 linhas curtas com fatos físicos que o narrador "
                                "deve obedecer até o próximo turno (onde está o saco, vela acesa ou apagada e "
                                "onde está, itens no chão por cômodo, o que está só no stash). Atualize sempre "
                                "que houver mudança de posse ou posição."
                            ),
                        },
                        "reason": {
                            "type": "string",
                            "description": "Justificativa curta para log técnico (PT-BR).",
                        },
                    },
                    "required": ["stash_add", "place_description_updates", "scene_facts", "reason"],
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
    dynamic_descriptions_before: dict[str, str],
    dynamic_details_before: dict[str, str],
    scene_facts_before: str,
) -> str:
    label = fatigue_label_for_context(fatigue_before)
    clock = format_game_clock_for_prompt(game_clock_before)
    tools_block = (
        "\n---\n".join(snap.tool_result_contents) if snap.tool_result_contents else "(nenhum resultado de tool neste turno)"
    )
    hidden = snap.hidden_beyond_player_perception.strip() or "(nada fornecido)"
    stash_line = ", ".join(stash_before) if stash_before else "(vazio)"
    place_keys = sorted(set(dynamic_descriptions_before) | set(dynamic_details_before))
    if place_keys:
        dynamic_lines = []
        for place_name in place_keys:
            description = dynamic_descriptions_before.get(place_name, "")
            details = dynamic_details_before.get(place_name, "")
            d_prev = description[:100] + ("..." if len(description) > 100 else "")
            t_prev = details[:100] + ("..." if len(details) > 100 else "")
            dynamic_lines.append(
                f"- {place_name}\n  basic_description: {d_prev or '(mapa)'}\n  details: {t_prev or '(mapa)'}"
            )
        dynamic_block = "\n".join(dynamic_lines)
    else:
        dynamic_block = "(nenhuma descrição dinâmica definida)"
    facts_block = scene_facts_before.strip() or "(nenhuma ficha de cena ainda)"
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
        f"- Descrições dinâmicas por lugar:\n{dynamic_block}\n\n"
        "### Fichas de cena atuais (fatos físicos para o narrador)\n"
        f"{facts_block}\n\n"
        "Chame **adjust_backstage_state** com **fatigue_delta** e **game_time_delta_minutes**. Se a narração "
        "não consolidou esforço, falha, manobra ou descanso **na ficção**, e não há sinal físico nos JSONs, "
        "use **fatigue_delta 0**. Se o turno for só troca de frases, esclarecimento ou foco no mesmo instante, "
        "use **game_time_delta_minutes 0** (ou poucos minutos se a prosa indicar pausa curta real).\n\n"
        "Quando houver mudança concreta de objetos no mundo (item pego, roubado, quebrado, consumido, "
        "sumido da cena), chame também **adjust_world_state** no mesmo turno para manter consistência: "
        "adicione item em `stash_add`, atualize **`basic_description` e `details`** completos do lugar afetado "
        "em `place_description_updates` e reescreva `scene_facts` para refletir posições e estados "
        "(mão, chão, stash, vela acesa, etc.)."
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


def _parse_world_adjust(
    arguments_json: str,
) -> tuple[list[str], list[tuple[str, str, str]], str, str]:
    raw = json.loads(arguments_json) if arguments_json else {}
    if not isinstance(raw, dict):
        raise ValueError("tool arguments must be an object")
    stash_raw = raw.get("stash_add", [])
    if not isinstance(stash_raw, list):
        raise ValueError("stash_add must be an array")
    stash_add = [str(item).strip() for item in stash_raw if str(item).strip()]

    updates_raw = raw.get("place_description_updates", [])
    if not isinstance(updates_raw, list):
        raise ValueError("place_description_updates must be an array")
    updates: list[tuple[str, str, str]] = []
    for item in updates_raw:
        if not isinstance(item, dict):
            continue
        place_name = str(item.get("place_name", "")).strip()
        basic_raw = item.get("basic_description", item.get("description", ""))
        if not isinstance(basic_raw, str):
            basic_raw = str(basic_raw) if basic_raw is not None else ""
        description = basic_raw.strip()
        det_raw = item.get("details", "")
        if not isinstance(det_raw, str):
            det_raw = str(det_raw) if det_raw is not None else ""
        details = det_raw.strip()
        if not place_name or not description:
            continue
        updates.append((place_name, description, details))

    scene_facts = raw.get("scene_facts", "")
    if not isinstance(scene_facts, str):
        scene_facts = str(scene_facts)
    scene_facts = scene_facts.strip()
    if (stash_add or updates) and not scene_facts:
        raise ValueError("scene_facts must be non-empty when stash_add or place_description_updates is non-empty")

    reason = raw.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)
    return stash_add, updates, scene_facts, reason.strip()


async def apply_backstage_llm(client: OpenAI, state: GameSessionState, snap: BackstageTurnSnapshot) -> None:
    async with state.lock:
        fatigue_before = state.fatigue_percent
        game_clock_before = state.game_clock_minutes
        stash_before = tuple(sorted(state.stash_items))
        dynamic_descriptions_before = dict(state.place_dynamic_descriptions)
        dynamic_details_before = dict(state.place_dynamic_details)
        scene_facts_before = state.scene_facts_sheet

    user_content = _build_backstage_user_content(
        snap,
        fatigue_before,
        game_clock_before,
        stash_before,
        dynamic_descriptions_before,
        dynamic_details_before,
        scene_facts_before,
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
                        stash_add, updates, scene_facts, reason = _parse_world_adjust(
                            str(tc.function.arguments or "")
                        )
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning("[%s] [backstage_llm] bad world args: %s", _hhmm(), e)
                        continue
                    async with state.lock:
                        before_stash = len(state.stash_items)
                        state.stash_items.update(stash_add)
                        changed_places = 0
                        for place_name, description, details in updates:
                            new_desc = _sanitize_model_text(description)
                            new_det = _sanitize_model_text(details)
                            prev_desc = state.place_dynamic_descriptions.get(place_name)
                            prev_det = state.place_dynamic_details.get(place_name)
                            if prev_desc != new_desc or prev_det != new_det:
                                changed_places += 1
                            state.place_dynamic_descriptions[place_name] = new_desc
                            state.place_dynamic_details[place_name] = new_det
                        if scene_facts:
                            state.scene_facts_sheet = _sanitize_model_text(scene_facts)
                        after_stash = len(state.stash_items)
                    tool_calls_executed += 1
                    logger.info(
                        "[%s] [backstage_llm] world stash +%d, places_changed=%d reason=%r",
                        _hhmm(),
                        after_stash - before_stash,
                        changed_places,
                        _sanitize_model_text(reason)[:200],
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
