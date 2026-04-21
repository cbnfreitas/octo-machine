import json
import os
from pathlib import Path

import app.logging_config  # noqa: F401 — configure uvicorn logger level
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
)
from tools import TOOLS, chat_system_content, run_tool

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

API_KEY = os.getenv("OPEN_AI_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
MAX_TOOL_ROUNDS = 8


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


async def _stream_model_round(
    client: OpenAI,
    ws: WebSocket,
    messages: list[ChatCompletionMessageParam],
) -> tuple[str, bool, list[ChatCompletionMessageFunctionToolCallParam]]:
    """
    One streamed completion with tools. Forwards only text deltas to the client.
    Returns (full_text, has_tool_calls, typed_calls). When has_tool_calls is True,
    typed_calls must be executed and the conversation continued.
    """
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        stream=True,
    )

    assistant_parts: list[str] = []
    tool_calls_by_index: dict[int, dict[str, object]] = {}

    for chunk in stream:
        choice = chunk.choices[0]
        delta = choice.delta
        if delta and delta.content:
            assistant_parts.append(delta.content)
            await ws.send_json({"type": "token", "text": delta.content})
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
        return full_text, False, []

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
    return full_text, True, typed_calls


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
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": chat_system_content()},
    ]

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

            turn_start = len(messages)
            messages.append({"role": "user", "content": content})

            try:
                round_num = 0
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

                    full_text, has_tools, typed_calls = await _stream_model_round(
                        client, ws, messages
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
                            result = run_tool(str(fn["name"]), str(fn["arguments"]))
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": str(tc["id"]),
                                    "content": result,
                                }
                            )
                        continue

                    messages.append({"role": "assistant", "content": full_text})
                    await ws.send_json({"type": "done"})
                    break

            except Exception as e:
                del messages[turn_start:]
                await ws.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        pass
