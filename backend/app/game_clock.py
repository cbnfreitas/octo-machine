"""
In-fiction clock for narrator context and backstage updates (minutes from midnight, 24h cycle).
"""

from __future__ import annotations

import re
from typing import Any

_CLOCK_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")


def parse_initial_game_time(value: Any) -> float:
    """Parse optional `initial_game_time` from game JSON (\"HH:MM\", 24h). Midnight is 00:00."""
    if value is None:
        return 0.0
    if not isinstance(value, str):
        raise TypeError("initial_game_time must be a string or absent")
    m = _CLOCK_RE.match(value.strip())
    if not m:
        raise ValueError(f"initial_game_time must look like HH:MM, got {value!r}")
    hour = int(m.group(1))
    minute = int(m.group(2))
    if hour == 24 and minute == 0:
        hour = 0
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        raise ValueError(f"initial_game_time out of range: {value!r}")
    return float(hour * 60 + minute)


def normalize_clock_minutes(total: float) -> float:
    wrapped = total % 1440.0
    if wrapped < 0:
        wrapped += 1440.0
    return wrapped


def format_game_clock_for_prompt(minutes: float) -> str:
    m = normalize_clock_minutes(minutes)
    total = int(m // 1) % 1440
    h = total // 60
    mi = total % 60
    return f"{h:02d}:{mi:02d}"
