from __future__ import annotations

import asyncio

from app.game_clock import normalize_clock_minutes


class GameSessionState:
    __slots__ = (
        "fatigue_percent",
        "game_clock_minutes",
        "places_entered_via_move",
        "known_place_names",
        "current_place_name",
        "stash_items",
        "place_dynamic_descriptions",
        "scene_facts_sheet",
        "_lock",
    )

    def __init__(self, *, initial_game_clock_minutes: float = 0.0) -> None:
        self.fatigue_percent = 0.0
        self.game_clock_minutes = normalize_clock_minutes(initial_game_clock_minutes)
        self.places_entered_via_move: set[str] = set()
        self.known_place_names: set[str] = set()
        self.current_place_name: str | None = None
        self.stash_items: set[str] = set()
        self.place_dynamic_descriptions: dict[str, str] = {}
        self.scene_facts_sheet: str = ""
        self._lock = asyncio.Lock()

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock
