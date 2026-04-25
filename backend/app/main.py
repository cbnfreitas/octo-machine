import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import app.logging_config  # noqa: F401 — configure uvicorn logger level
from app.logging_config import logger, yellow_tool
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
)
from app.messaging import build_turn_user_content
from app.backstage import BackstageTurnSnapshot, apply_backstage_llm
from app.feature_flags import scene_images_enabled
from app.session_state import GameSessionState
from app.system_prompt import (
    OPENING_USER_PLACEHOLDER,
    chat_system_content,
    fallback_opening_message,
    opening_turn_user_content,
)
from tools import TOOLS, run_tool
from tools.move import (
    get_game_fixed_intro,
    get_initial_game_clock_minutes,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GAME_STATIC_ROOT = Path(__file__).resolve().parent / "game"
load_dotenv(REPO_ROOT / ".env")

API_KEY = os.getenv("OPEN_AI_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
MAX_TOOL_ROUNDS = 8


def _hhmm() -> str:
    return datetime.now().strftime("%H:%M")


async def _push_scene_image_from_move_result(ws: WebSocket, tool_name: str, result_json: str) -> None:
    if not scene_images_enabled():
        return
    if tool_name != "move":
        return
    try:
        data = json.loads(result_json)
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
        return
    pimg = data.get("place_scene_image")
    if not isinstance(pimg, dict):
        return
    url = pimg.get("url")
    pname = pimg.get("place_name", "")
    if not isinstance(url, str) or not url.startswith("/"):
        return
    await ws.send_json(
        {
            "type": "scene_image",
            "url": url,
            "place_name": pname if isinstance(pname, str) else "",
        }
    )


async def _run_backstage_turn(
    client: OpenAI, state: GameSessionState, snap: BackstageTurnSnapshot
) -> None:
    try:
        await apply_backstage_llm(client, state, snap)
    except Exception:
        logger.exception("%s [backstage] turn failed", _hhmm())


def _streamed_tool_calls_are_complete(tool_calls_list: list[dict[str, object]]) -> bool:
    if not tool_calls_list:
        return False
    for tc in tool_calls_list:
        fn = tc.get("function")
        if not isinstance(fn, dict):
            return False
        if not str(tc.get("id", "")).strip():
            return False
        if not str(fn.get("name", "")).strip():
            return False
    return True


app = FastAPI(title="Octo Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/game", StaticFiles(directory=str(GAME_STATIC_ROOT)), name="game_assets")


async def _stream_model_round(
    client: OpenAI,
    ws: WebSocket,
    messages: list[ChatCompletionMessageParam],
    *,
    forward_tokens: bool = True,
    use_tools: bool = True,
    buffer_tokens_until_tool_round_complete: bool = False,
) -> tuple[str, bool, list[ChatCompletionMessageFunctionToolCallParam], int, list[str]]:
    """
    One streamed completion. Forwards text deltas to the client when forward_tokens is True.
    Returns (full_text, has_tool_calls, typed_calls, forwarded_token_events, pending_token_chunks).
    When has_tool_calls is True, typed_calls must be executed and the conversation continued.
    If buffer_tokens_until_tool_round_complete and use_tools, content deltas are held in
    pending_token_chunks until the caller runs tools and scene_image, then the caller must
    forward them — so narration does not appear before move + scene_image in the same turn.
    """
    if use_tools:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            stream=True,
            stream_options={"include_usage": True},
        )
    else:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )

    assistant_parts: list[str] = []
    tool_calls_by_index: dict[int, dict[str, object]] = {}
    forwarded_token_events = 0
    pending_token_chunks: list[str] = []
    buffer_mode = bool(
        forward_tokens and use_tools and buffer_tokens_until_tool_round_complete
    )

    for chunk in stream:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        delta = choice.delta
        if delta and delta.content:
            assistant_parts.append(delta.content)
            if forward_tokens:
                if buffer_mode:
                    pending_token_chunks.append(delta.content)
                else:
                    await ws.send_json({"type": "token", "text": delta.content})
                    forwarded_token_events += 1
        if delta and delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_by_index:
                    tool_calls_by_index[idx] = {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                if tc.id:
                    tool_calls_by_index[idx]["id"] = tc.id
                if tc.function:
                    fn = tool_calls_by_index[idx]["function"]
                    assert isinstance(fn, dict)
                    if tc.function.name:
                        fn["name"] = tc.function.name
                    if tc.function.arguments:
                        fn["arguments"] = str(fn["arguments"]) + tc.function.arguments

    full_text = "".join(assistant_parts)
    tool_calls_list = [tool_calls_by_index[i] for i in sorted(tool_calls_by_index)]
    # Streaming sometimes omits finish_reason == "tool_calls" in edge cases; trust merged calls.
    has_tools = _streamed_tool_calls_are_complete(tool_calls_list)

    if not has_tools:
        if buffer_mode and pending_token_chunks:
            for piece in pending_token_chunks:
                await ws.send_json({"type": "token", "text": piece})
                forwarded_token_events += 1
        return full_text, False, [], forwarded_token_events, []

    typed_calls: list[ChatCompletionMessageFunctionToolCallParam] = []
    for tc in tool_calls_list:
        fn = tc["function"]
        assert isinstance(fn, dict)
        typed_calls.append(
            {
                "id": str(tc["id"]),
                "type": "function",
                "function": {
                    "name": str(fn["name"]),
                    "arguments": str(fn["arguments"]),
                },
            }
        )
    return (
        full_text,
        True,
        typed_calls,
        forwarded_token_events,
        list(pending_token_chunks) if buffer_mode else [],
    )


@app.get("/health")
def health():
    return {"ok": True}


@app.websocket("/ws/chat")
async def chat(ws: WebSocket):
    await ws.accept()
    if not API_KEY:
        await ws.send_json(
            {"type": "error", "message": "Missing OPEN_AI_API_KEY or OPENAI_API_KEY in .env"}
        )
        await ws.close()
        return

    client = OpenAI(api_key=API_KEY)
    session_state = GameSessionState(initial_game_clock_minutes=get_initial_game_clock_minutes())
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": chat_system_content()},
        {
            "role": "user",
            "content": opening_turn_user_content(
                fatigue_percent=session_state.fatigue_percent,
                game_clock_minutes=session_state.game_clock_minutes,
            ),
        },
    ]
    fixed_intro_text = get_game_fixed_intro()
    if fixed_intro_text:
        await ws.send_json({"type": "fixed_intro", "text": fixed_intro_text})
    await ws.send_json({"type": "opening_start"})

    opening_text = ""
    opening_forwarded_tokens = 0
    try:
        try:
            round_num = 0
            while True:
                round_num += 1
                if round_num > MAX_TOOL_ROUNDS:
                    raise RuntimeError("Tool loop limit reached in opening turn")
                opening_text, has_tools, typed_calls, round_forwarded, pending_token_chunks = (
                    await _stream_model_round(
                        client,
                        ws,
                        messages,
                        buffer_tokens_until_tool_round_complete=True,
                    )
                )
                opening_forwarded_tokens += round_forwarded
                if has_tools:
                    opening_asst_msg: ChatCompletionAssistantMessageParam = {
                        "role": "assistant",
                        "tool_calls": typed_calls,
                    }
                    if opening_text:
                        opening_asst_msg["content"] = opening_text
                    messages.append(opening_asst_msg)

                    for tc in typed_calls:
                        fn = tc["function"]
                        assert isinstance(fn, dict)
                        tname = str(fn["name"])
                        targs = str(fn.get("arguments", ""))
                        logger.info(
                            "[%s] [narrator_llm -> engine] tool_call id=%s name=%s args=%s",
                            _hhmm(),
                            str(tc.get("id", "")),
                            yellow_tool(tname),
                            targs[:4000] + ("…" if len(targs) > 4000 else ""),
                        )
                        result = await run_tool(tname, targs, session_state=session_state)
                        await _push_scene_image_from_move_result(ws, tname, result)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": str(tc["id"]),
                                "content": result,
                            }
                        )
                    for piece in pending_token_chunks:
                        await ws.send_json({"type": "token", "text": piece})
                    continue
                opening_text = opening_text.strip()
                break
        except Exception:
            logger.exception("[chat] opening generation failed; using fallback text")
            opening_text = ""
        if not opening_text:
            opening_text = fallback_opening_message(session_state=session_state).strip()
        if opening_forwarded_tokens == 0 and opening_text:
            await ws.send_json({"type": "token", "text": opening_text})
    finally:
        await ws.send_json({"type": "opening_done"})

    messages.append({"role": "assistant", "content": opening_text})
    messages[1] = {"role": "user", "content": OPENING_USER_PLACEHOLDER}

    pending_backstage: asyncio.Task | None = None

    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            content = (payload.get("content") or "").strip()
            if not content:
                continue

            if pending_backstage is not None:
                if not pending_backstage.done():
                    await ws.send_json({"type": "backstage_pending"})
                    try:
                        await pending_backstage
                    except Exception:
                        logger.exception("[%s] [chat] wait for backstage failed", _hhmm())
                pending_backstage = None

            turn_start = len(messages)
            async with session_state.lock:
                fatigue_now = session_state.fatigue_percent
                clock_now = session_state.game_clock_minutes
                known_now = tuple(sorted(session_state.known_place_names))
                current_now = session_state.current_place_name
            messages.append(
                {
                    "role": "user",
                    "content": build_turn_user_content(
                        content,
                        fatigue_percent=fatigue_now,
                        game_clock_minutes=clock_now,
                        current_place_name=current_now,
                        known_place_names=known_now,
                    ),
                }
            )

            try:
                round_num = 0
                turn_tool_results: list[str] = []
                while True:
                    round_num += 1
                    if round_num > MAX_TOOL_ROUNDS:
                        del messages[turn_start:]
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": "Tool loop limit reached; try a simpler request.",
                            }
                        )
                        break

                    full_text, has_tools, typed_calls, _, pending_token_chunks = (
                        await _stream_model_round(
                            client,
                            ws,
                            messages,
                            buffer_tokens_until_tool_round_complete=True,
                        )
                    )

                    if has_tools:
                        asst_msg: ChatCompletionAssistantMessageParam = {
                            "role": "assistant",
                            "tool_calls": typed_calls,
                        }
                        if full_text:
                            asst_msg["content"] = full_text
                        messages.append(asst_msg)

                        for tc in typed_calls:
                            fn = tc["function"]
                            assert isinstance(fn, dict)
                            tname = str(fn["name"])
                            targs = str(fn.get("arguments", ""))
                            logger.info(
                                "[%s] [narrator_llm -> engine] tool_call id=%s name=%s args=%s",
                                _hhmm(),
                                str(tc.get("id", "")),
                                yellow_tool(tname),
                                targs[:4000] + ("…" if len(targs) > 4000 else ""),
                            )
                            result = await run_tool(tname, targs, session_state=session_state)
                            await _push_scene_image_from_move_result(ws, tname, result)
                            turn_tool_results.append(result)
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": str(tc["id"]),
                                    "content": result,
                                }
                            )
                        for piece in pending_token_chunks:
                            await ws.send_json({"type": "token", "text": piece})
                        continue

                    messages.append({"role": "assistant", "content": full_text})
                    snap = BackstageTurnSnapshot(
                        player_intent_plain=content,
                        narration_to_player=full_text,
                        tool_result_contents=list(turn_tool_results),
                    )
                    await ws.send_json({"type": "done"})
                    pending_backstage = asyncio.create_task(
                        _run_backstage_turn(client, session_state, snap)
                    )
                    break

            except Exception as e:
                del messages[turn_start:]
                await ws.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        pass
