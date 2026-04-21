import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from openai.types.chat import ChatCompletionToolUnionParam

from .invoke import invoke_tool

_GAME_MAP_JSON = Path(__file__).resolve().parent.parent / "app" / "game" / "casa_fatso.json"
STARTING_PLACE_NAME = "Entrada"

TOOL_SYSTEM_INSTRUCTION = (
    "Quando o jogador **mudar de lugar** ou **ir para outro cômodo**, chame `move` com "
    "`place_name` **exatamente** como no mapa (ex.: \"Entrada\", \"Salão\", \"Despensa\"). "
    "A saída traz `description` e `player_facing_summary` **já filtrados** (sem blocos de "
    "segredo/armadilha do arquivo bruto); use isso como base ao chegar. O campo `description_full` "
    "é o texto integral do mapa—**só** use trechos ocultos quando o jogador **tiver explorado "
    "de forma pertinente**; nunca copie `description_full` inteiro de uma vez para o jogador."
)

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "move",
        "description": (
            "Registra a chegada do jogador a um lugar do mapa. Devolve a descrição do ambiente, "
            "os destinos ligados a ele e um resumo para você narrar. Use quando o jogador for "
            "para outro cômodo ou ao resolver deslocamento."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "place_name": {
                    "type": "string",
                    "description": (
                        "Nome do lugar conforme o mapa, sem inventar (ex.: "
                        "\"Entrada\", \"Sala Principal\", \"Depósito Subterrâneo\")."
                    ),
                },
            },
            "required": ["place_name"],
        },
    },
}


@lru_cache(maxsize=1)
def _place_index() -> dict[str, dict[str, Any]]:
    with _GAME_MAP_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    raw_places = data["places"]
    if not isinstance(raw_places, list):
        raise TypeError("game map JSON: 'places' must be a list")
    index: dict[str, dict[str, Any]] = {}
    for item in raw_places:
        if not isinstance(item, dict):
            continue
        name = item.get("place_name")
        if isinstance(name, str) and name:
            index[name] = item
    return index


def _format_connection_line(connections: list[str]) -> str:
    if not connections:
        return "Não há outras saídas indicadas a partir daqui."
    if len(connections) == 1:
        return f"A partir daqui você pode ir para {connections[0]}."
    if len(connections) == 2:
        return (
            f"A partir daqui você pode ir para {connections[0]} ou {connections[1]}."
        )
    *rest, last = connections
    return "A partir daqui você pode ir para " + ", ".join(rest) + f" e {last}."


# Strips spoiler blocks from raw map prose (labels like "Segredo:" / "Armadilha:" and the rest of
# the string from that point). Does not match "segredos" without an immediate label colon.
_SECRET_TAIL = re.compile(
    r"\s*\bSegredos?(?:\s+importante|\s+crítico)?\s*:.*",
    re.IGNORECASE | re.DOTALL,
)
_ARMADILHA_TAIL = re.compile(
    r"\s*\bArmadilha\s*:.*",
    re.IGNORECASE | re.DOTALL,
)


def _description_for_player_facing(raw: str) -> str:
    text = raw.strip()
    text = _SECRET_TAIL.sub("", text)
    text = _ARMADILHA_TAIL.sub("", text)
    return " ".join(text.split())


def move_to_place(place_name: str) -> dict[str, object]:
    trimmed = place_name.strip()
    if not trimmed:
        raise ValueError("place_name must be a non-empty string")

    entry = _place_index().get(trimmed)
    if entry is None:
        raise ValueError(f"Unknown place_name: {trimmed!r}")

    raw_conns = entry.get("connections", [])
    if not isinstance(raw_conns, list):
        raise TypeError("connections must be a list")
    connections = [c for c in raw_conns if isinstance(c, str)]

    description_full = entry.get("description", "")
    if not isinstance(description_full, str):
        description_full = str(description_full)

    description = _description_for_player_facing(description_full)

    connection_line = _format_connection_line(connections)
    player_facing_summary = f"{description}\n\n{connection_line}"

    return {
        "place_name": trimmed,
        "description": description,
        "description_full": description_full,
        "connections": connections,
        "player_facing_summary": player_facing_summary,
    }


def run(arguments_json: str) -> str:
    def execute(args: dict[str, Any]) -> dict[str, object]:
        name = args["place_name"]
        if not isinstance(name, str):
            raise TypeError("place_name must be a string")
        return move_to_place(name)

    return invoke_tool(
        "move",
        arguments_json,
        execute,
        log_line=lambda r: "place_name=%r connections=%s"
        % (r["place_name"], r["connections"]),
    )
