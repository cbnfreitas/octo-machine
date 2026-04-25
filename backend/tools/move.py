import difflib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from openai.types.chat import ChatCompletionToolUnionParam

from app.game_clock import parse_initial_game_time
from app.feature_flags import scene_images_enabled
from app.session_state import GameSessionState

from .invoke import invoke_tool

_GAME_MAP_JSON = Path(__file__).resolve().parent.parent / "app" / "game" / "uma_noite_de_trabalho.json"
GAME_MAP_BASENAME = _GAME_MAP_JSON.name
STARTING_PLACE_NAME = "Cozinha"

def _tool_system_instruction() -> str:
    base = (
        "Quando o jogador **mudar de lugar** ou **ir para outro cômodo**, chame `move` com "
        "`place_name` no **nome canônico** do mapa (como nas chaves de local do ficheiro JSON). "
        "Quem interpreta a fala natural do jogador e escolhe o destino correto é **você**; a tool só "
        "recebe o nome já resolvido. "
        "A saída traz **`basic_description`** (camada principal, impressão imediata) e "
        "`player_facing_summary` **já filtrados** (sem blocos de segredo/armadilha do arquivo bruto). "
        "Na **primeira entrada** a um lugar nesta sessão (`revisit`: false), **não** enviamos o campo "
        "**`details`** no JSON (fica reservado ao motor e ao backstage); a narração de chegada deve "
        "apoiar-se **só** em `basic_description` e conexões. Quando **`revisit`: true**, o JSON inclui "
        "**`details`** (camada extra) para aprofundar. O campo **`description_full`** na primeira visita "
        "coincide com `basic_description`; em revisit junta as duas camadas filtradas—**só** use "
        "trechos ocultos quando o jogador **tiver explorado "
        "de forma pertinente**; nunca copie `description_full` inteiro de uma vez para o jogador. "
        "`connections` é uma lista de objetos com `to`, `how` e sinalizadores de passagem; use `how` "
        "como base perceptiva (ver regras de POV no system prompt). "
        "Quando origem e destino não forem adjacentes, `move` pode resolver deslocamento em múltiplas "
        "etapas por nós já visitados e retorna também o caminho percorrido."
    )
    if scene_images_enabled():
        return (
            f"{base} Na **primeira vez** que o `move` registra a entrada a um lugar **nesta sessão**, "
            "se existir ilustração na pasta do jogo (pasta do mapa, ficheiro `<slug-do-lugar>.png` "
            "ou semelhante), o JSON inclui **`place_scene_image`** com `url` — a interface do jogador "
            "**mostra** essa arte automaticamente; integre a cena na prosa sem contradizer o visual."
        )
    return base


TOOL_SYSTEM_INSTRUCTION = _tool_system_instruction()

TOOL: ChatCompletionToolUnionParam = {
    "type": "function",
    "function": {
        "name": "move",
        "description": (
            "Registra a chegada do jogador a um lugar do mapa. Devolve a descrição do ambiente, "
            "os destinos ligados a ele, o caminho percorrido e um resumo para você narrar. "
            "Use quando o jogador for para outro cômodo ou ao resolver deslocamento."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "place_name": {
                    "type": "string",
                    "description": (
                        "Nome **canônico** do lugar no mapa (o que você inferiu a partir da intenção do jogador). "
                        "Deve coincidir com um `location_name` / destino `to` válido. "
                        "Use UTF-8 real: **não** use escapes Unicode no meio do nome (ex.: o trecho \"ão\" em "
                        "\"Porão\", não um caractere nulo)."
                    ),
                },
            },
            "required": ["place_name"],
        },
    },
}


@lru_cache(maxsize=1)
def _raw_game_document() -> dict[str, Any]:
    with _GAME_MAP_JSON.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_player_narrative_filters() -> tuple[str, ...]:
    raw = _raw_game_document().get("player_narrative_filters")
    if not isinstance(raw, list):
        return ()
    out: list[str] = []
    for item in raw:
        s = str(item).strip() if item is not None else ""
        if s:
            out.append(s)
    return tuple(out)


def _place_index() -> dict[str, dict[str, Any]]:
    data = _raw_game_document()
    raw_regions = data.get("regions")
    raw_places = data.get("places")
    containers: list[dict[str, Any]] = []

    if isinstance(raw_regions, list):
        containers.extend(item for item in raw_regions if isinstance(item, dict))
    if isinstance(raw_places, list):
        containers.extend(item for item in raw_places if isinstance(item, dict))
    if not containers:
        raise TypeError("game map JSON: expected 'regions' or 'places' as a list")

    index: dict[str, dict[str, Any]] = {}
    for container in containers:
        parent_name = container.get("region_name")
        if not isinstance(parent_name, str) or not parent_name.strip():
            parent_name = container.get("place_name")
        raw_locations = container.get("locations")
        raw_rooms = container.get("rooms")

        location_items: list[dict[str, Any]] = []
        if isinstance(raw_locations, list):
            location_items.extend(item for item in raw_locations if isinstance(item, dict))
        if isinstance(raw_rooms, list):
            location_items.extend(item for item in raw_rooms if isinstance(item, dict))

        for loc in location_items:
            location_name = loc.get("location_name")
            if not isinstance(location_name, str) or not location_name.strip():
                location_name = loc.get("room_name")
            if not isinstance(location_name, str) or not location_name.strip():
                continue
            location_entry = dict(loc)
            if isinstance(parent_name, str) and parent_name.strip():
                location_entry["parent_place_name"] = parent_name
            index[location_name] = location_entry
    return index


def get_game_fixed_intro() -> str:
    raw = _raw_game_document().get("fixed_intro")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def get_narrator_opening_note() -> str:
    raw = _raw_game_document().get("narrator_opening_note")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def get_initial_game_clock_minutes() -> float:
    raw = _raw_game_document().get("initial_game_time")
    return parse_initial_game_time(raw)


def _game_media_root() -> Path:
    return _GAME_MAP_JSON.parent / _GAME_MAP_JSON.stem


def _place_image_slug(place_name: str) -> str:
    decomposed = unicodedata.normalize("NFD", place_name.casefold())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "_", stripped.strip("_"))
    return slug or "place"


def _find_scene_image_file(place_name: str) -> Path | None:
    root = _game_media_root()
    if not root.is_dir():
        return None
    slug = _place_image_slug(place_name)
    for ext in (".png", ".webp", ".jpg", ".jpeg"):
        candidate = root / f"{slug}{ext}"
        if candidate.is_file():
            return candidate
    try:
        for p in root.iterdir():
            if not p.is_file():
                continue
            stem = p.stem.casefold()
            if stem == slug or stem == place_name.casefold():
                if p.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}:
                    return p
    except OSError:
        return None
    return None


def _public_scene_image_path(place_name: str) -> str | None:
    path = _find_scene_image_file(place_name)
    if path is None:
        return None
    rel = path.relative_to(_GAME_MAP_JSON.parent)
    return "/game/" + rel.as_posix()


def public_scene_image_url_for_place(place_name: str) -> str | None:
    """`/game/...` URL when a scene image file exists for this place (no visit tracking)."""
    return _public_scene_image_path(place_name)


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


_NON_TRAVERSABLE_TOKENS = (
    "não dá passagem",
    "nao da passagem",
    "só visão",
    "so visao",
    "apenas visão",
    "apenas visao",
    "sem passagem",
)

_HIDDEN_TOKENS = (
    "secreto",
    "oculto",
    "escondido",
    "mecanismo secreto",
    "alçapão",
    "alcapao",
)


def _connection_is_hidden(how: str) -> bool:
    folded = _fold_for_match(how)
    return any(token in folded for token in _HIDDEN_TOKENS)


def _connection_seems_traversable(how: str) -> bool:
    folded = _fold_for_match(how)
    return not any(token in folded for token in _NON_TRAVERSABLE_TOKENS)


def _extract_connections_from_entry(entry: dict[str, Any]) -> list[dict[str, object]]:
    raw_conns = entry.get("connections", [])
    if not isinstance(raw_conns, list):
        raise TypeError("connections must be a list")

    connections: list[dict[str, object]] = []
    for conn in raw_conns:
        if not isinstance(conn, dict):
            continue
        to_raw = conn.get("to")
        how_raw = conn.get("how")
        to = to_raw.strip() if isinstance(to_raw, str) else ""
        how = how_raw.strip() if isinstance(how_raw, str) else ""
        if not to or not how:
            continue
        hidden = _connection_is_hidden(how)
        traversable = _connection_seems_traversable(how) and not hidden
        public_how = how
        if hidden:
            public_how = "ligação oculta (não perceptível sem investigação)"
        connections.append(
            {
                "to": to,
                "how": public_how,
                "how_raw": how,
                "destination_hidden_until_discovery": hidden,
                "seems_traversable_now": traversable,
            }
        )
    return connections


def _build_shortest_path(
    *,
    current: str,
    target: str,
    index: dict[str, dict[str, Any]],
    visited_nodes: set[str],
) -> list[str] | None:
    if current == target:
        return [current]
    allowed_nodes = set(visited_nodes)
    allowed_nodes.add(current)
    allowed_nodes.add(target)

    queue: list[str] = [current]
    prev: dict[str, str | None] = {current: None}
    q_idx = 0

    while q_idx < len(queue):
        node = queue[q_idx]
        q_idx += 1
        node_entry = index.get(node)
        if node_entry is None:
            continue
        for conn in _extract_connections_from_entry(node_entry):
            if not bool(conn.get("seems_traversable_now", False)):
                continue
            nxt = str(conn["to"])
            if nxt not in allowed_nodes:
                continue
            if nxt in prev:
                continue
            prev[nxt] = node
            if nxt == target:
                queue = []
                break
            queue.append(nxt)

    if target not in prev:
        return None

    path: list[str] = []
    step: str | None = target
    while step is not None:
        path.append(step)
        step = prev[step]
    path.reverse()
    return path


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


def _static_place_layer(entry: dict[str, Any], key: str, *, alt_key: str | None = None) -> str:
    raw = entry.get(key, "")
    if (not isinstance(raw, str) or not str(raw).strip()) and alt_key:
        raw = entry.get(alt_key, "")
    if not isinstance(raw, str):
        return str(raw) if raw is not None else ""
    return raw.strip()


def _place_layers_for_session(
    place_name: str,
    entry: dict[str, Any],
    *,
    session_state: GameSessionState | None = None,
) -> tuple[str, str]:
    main = _static_place_layer(entry, "basic_description", alt_key="description")
    det = _static_place_layer(entry, "details")
    if session_state is None:
        return main, det
    dyn_main = session_state.place_dynamic_descriptions.get(place_name)
    if isinstance(dyn_main, str) and dyn_main.strip():
        main = dyn_main.strip()
    dyn_det = session_state.place_dynamic_details.get(place_name)
    if isinstance(dyn_det, str) and dyn_det.strip():
        det = dyn_det.strip()
    return main, det


def _strip_control_chars(s: str) -> str:
    # NUL often appears when a model emits \u0000 instead of \u00e3 (ã) in JSON.
    return "".join(ch for ch in s if ch != "\x00")


def _repair_common_model_corruptions(s: str) -> str:
    # After stripping NUL, "Porão" may become "Pore3o" (broken \u00e3 → \u0000e3).
    t = re.sub(r"(?i)Pore3o", "Porão", s)
    return t


def _fold_for_match(s: str) -> str:
    decomposed = unicodedata.normalize("NFD", s.casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _resolve_place_name(raw: str, index: dict[str, dict[str, Any]]) -> str | None:
    names = list(index.keys())
    if not names:
        return None

    s = unicodedata.normalize("NFC", _strip_control_chars(raw.strip()))
    if not s:
        return None

    collapsed = re.sub(r"[\s\-–—]+", " ", s).strip()
    variants = [s, collapsed, _repair_common_model_corruptions(s)]
    for candidate in variants:
        if candidate in index:
            return candidate

    folded_in = _fold_for_match(s)
    for name in names:
        if _fold_for_match(name) == folded_in:
            return name

    for candidate in variants:
        matches = difflib.get_close_matches(candidate, names, n=1, cutoff=0.72)
        if matches:
            return matches[0]

    return None


def move_to_place(
    place_name: str, *, session_state: GameSessionState | None = None
) -> dict[str, object]:
    trimmed = place_name.strip()
    if not trimmed:
        raise ValueError("place_name must be a non-empty string")

    index = _place_index()
    resolved = _resolve_place_name(trimmed, index)
    if resolved is None:
        hint = ""
        s = _repair_common_model_corruptions(_strip_control_chars(trimmed))
        near = difflib.get_close_matches(s, list(index.keys()), n=3, cutoff=0.4)
        if near:
            hint = f" Sugestões: {', '.join(near)}."
        raise ValueError(f"Unknown place_name: {trimmed!r}.{hint}")

    path_taken = [resolved]
    if session_state is not None and session_state.current_place_name is not None:
        current = session_state.current_place_name
        current_entry = index.get(current)
        if current_entry is not None:
            current_connections = _extract_connections_from_entry(current_entry)
            allowed = {
                str(c["to"])
                for c in current_connections
                if bool(c.get("seems_traversable_now", False))
            }
            if resolved != current and resolved not in allowed:
                visited_nodes = set(session_state.known_place_names)
                visited_nodes.add(current)
                shortest_path = _build_shortest_path(
                    current=current,
                    target=resolved,
                    index=index,
                    visited_nodes=visited_nodes,
                )
                if shortest_path is None:
                    allowed_hint = ", ".join(sorted(allowed)) if allowed else "(nenhuma passagem direta)"
                    raise ValueError(
                        f"Invalid move from {current!r} to {resolved!r}. "
                        f"Conexões diretas válidas agora: {allowed_hint}."
                    )
                path_taken = shortest_path
            else:
                path_taken = [current, resolved] if resolved != current else [current]

    entry = index[resolved]
    connections = _extract_connections_from_entry(entry)

    is_revisit = False
    if session_state is not None:
        is_revisit = resolved in session_state.places_entered_via_move

    main_raw, details_raw = _place_layers_for_session(resolved, entry, session_state=session_state)
    basic_description = _description_for_player_facing(main_raw)
    details = _description_for_player_facing(details_raw)
    if is_revisit:
        description_full = basic_description + (
            "\n\n" + details if details.strip() else ""
        )
    else:
        description_full = basic_description

    public_connection_hows = [
        str(c["how"])
        for c in connections
        if not bool(c.get("destination_hidden_until_discovery", False))
        and bool(c.get("seems_traversable_now", False))
    ]
    connection_line = _format_connection_line(public_connection_hows)

    player_facing_summary = f"{basic_description}\n\n{connection_line}"

    result: dict[str, object] = {
        "place_name": resolved,
        "path_taken": path_taken,
        "revisit": is_revisit,
        "basic_description": basic_description,
        "description_full": description_full,
        "connections": connections,
        "player_facing_summary": player_facing_summary,
    }
    if is_revisit and details.strip():
        result["details"] = details

    if session_state is not None:
        first_visit = not is_revisit
        public = _public_scene_image_path(resolved)
        if scene_images_enabled() and first_visit and public is not None:
            result["place_scene_image"] = {
                "url": public,
                "place_name": resolved,
                "note": "First visit this session; scene image feature is enabled.",
            }
        session_state.places_entered_via_move.add(resolved)
        session_state.known_place_names.add(resolved)
        session_state.current_place_name = resolved

    return result


def run(arguments_json: str, *, session_state: GameSessionState | None = None) -> str:
    def execute(args: dict[str, Any]) -> dict[str, object]:
        name = args["place_name"]
        if not isinstance(name, str):
            raise TypeError("place_name must be a string")
        return move_to_place(name, session_state=session_state)

    def _move_log_line(r: dict[str, object]) -> str:
        raw_conns = r.get("connections")
        raw_path = r.get("path_taken")
        dests: list[object] = []
        path_taken: list[object] = []
        if isinstance(raw_conns, list):
            for c in raw_conns:
                if isinstance(c, dict) and "to" in c:
                    dests.append(c["to"])
        if isinstance(raw_path, list):
            path_taken.extend(raw_path)
        return "place_name=%r revisit=%s path=%s dests=%s scene=%s" % (
            r["place_name"],
            r.get("revisit"),
            path_taken,
            dests,
            "yes" if r.get("place_scene_image") else "no",
        )

    return invoke_tool(
        "move",
        arguments_json,
        execute,
        log_line=_move_log_line,
    )
