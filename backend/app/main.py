import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

API_KEY = os.getenv("OPEN_AI_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = FastAPI(title="Octo Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": "You are a helpful assistant. Reply concisely."}
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

            messages.append({"role": "user", "content": content})

            try:
                stream = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    stream=True,
                )
            except Exception as e:
                await ws.send_json({"type": "error", "message": str(e)})
                messages.pop()
                continue

            assistant_parts: list[str] = []
            try:
                for chunk in stream:
                    choice = chunk.choices[0]
                    delta = choice.delta.content if choice.delta else None
                    if delta:
                        assistant_parts.append(delta)
                        await ws.send_json({"type": "token", "text": delta})
            except Exception as e:
                await ws.send_json({"type": "error", "message": str(e)})
                messages.pop()
                continue

            full = "".join(assistant_parts)
            messages.append({"role": "assistant", "content": full})
            await ws.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass
