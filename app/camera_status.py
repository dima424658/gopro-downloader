"""Small in-process cache for camera status shown in the desktop window."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

_lock = threading.Lock()
_battery_percent: int | None = None


def battery_percent_from_state(state: Mapping[Any, Any]) -> int | None:
    """Extract the internal battery percentage from an Open GoPro camera state."""
    for status_id, value in state.items():
        if "INTERNAL_BATTERY_PERCENTAGE" not in str(status_id):
            continue
        try:
            percent = int(value)
        except (TypeError, ValueError):
            return None
        return percent if 0 <= percent <= 100 else None
    return None


def set_battery_percent(value: int | None) -> None:
    global _battery_percent
    with _lock:
        _battery_percent = value


def get_battery_percent() -> int | None:
    with _lock:
        return _battery_percent
