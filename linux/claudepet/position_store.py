"""Port of PetPositionStore.swift, backed by JSON instead of UserDefaults.

Position is stored as a *fraction* of the screen's available geometry rather than
absolute pixels, and keyed by a stable screen identity, so unplugging a monitor
or changing resolution doesn't strand the pet off-screen. Restore always clamps
back into the current screen's bounds.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication, QScreen

from . import paths


def _screen_id(screen: QScreen) -> str:
    """Stable per-display identity — the Linux stand-in for macOS's
    CGDisplayCreateUUIDFromDisplayID. Serial number when the monitor reports one
    (typically only under X11/EDID), otherwise the name (e.g. "eDP-1"), which is
    at least stable across a session on both X11 and Wayland."""
    serial = (screen.serialNumber() or "").strip()
    if serial:
        return f"serial:{serial}"
    return f"name:{screen.name()}"


def _find_screen(screen_id: str) -> QScreen | None:
    for screen in QGuiApplication.screens():
        if _screen_id(screen) == screen_id:
            return screen
    return None


def _read() -> dict:
    try:
        with open(paths.state_file(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    try:
        paths.state_dir().mkdir(parents=True, exist_ok=True)
        with open(paths.state_file(), "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except OSError:
        # Losing the remembered position is not worth interrupting the user over.
        pass


def save_position(top_left: QPoint, screen: QScreen | None) -> None:
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        return

    available = screen.availableGeometry()
    if available.width() <= 0 or available.height() <= 0:
        return

    data = _read()
    data["position"] = {
        "screen": _screen_id(screen),
        "x_fraction": (top_left.x() - available.x()) / available.width(),
        "y_fraction": (top_left.y() - available.y()) / available.height(),
    }
    _write(data)


def load_position(size_width: int, size_height: int) -> QPoint | None:
    stored = _read().get("position")
    if not isinstance(stored, dict):
        return None

    screen = _find_screen(str(stored.get("screen", "")))
    if screen is None:
        return None

    try:
        x_fraction = float(stored["x_fraction"])
        y_fraction = float(stored["y_fraction"])
    except (KeyError, TypeError, ValueError):
        return None

    available = screen.availableGeometry()
    x = available.x() + x_fraction * available.width()
    y = available.y() + y_fraction * available.height()

    max_x = available.x() + available.width() - size_width
    max_y = available.y() + available.height() - size_height
    clamped_x = int(min(max(x, available.x()), max(max_x, available.x())))
    clamped_y = int(min(max(y, available.y()), max(max_y, available.y())))
    return QPoint(clamped_x, clamped_y)


def default_position(size_width: int, size_height: int) -> QPoint:
    """Bottom-right-ish of the primary screen, matching the macOS default."""
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return QPoint(100, 100)
    available = screen.availableGeometry()
    x = available.x() + available.width() - size_width - 100
    y = available.y() + available.height() - size_height - 100
    return QPoint(max(available.x(), int(x)), max(available.y(), int(y)))


def save_sleep_timeout(seconds: float) -> None:
    data = _read()
    data["sleep_timeout"] = seconds
    _write(data)


def load_sleep_timeout(default: float) -> float:
    value = _read().get("sleep_timeout")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return default
