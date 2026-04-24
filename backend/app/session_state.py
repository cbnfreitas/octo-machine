from __future__ import annotations

import asyncio


class GameSessionState:
    __slots__ = ("fatigue_percent", "_lock")

    def __init__(self) -> None:
        self.fatigue_percent = 0.0
        self._lock = asyncio.Lock()

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock
