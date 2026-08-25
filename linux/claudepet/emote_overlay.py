"""Port of EmoteOverlay.swift, drawn with QPainter.

Coordinates in the public API stay in the macOS convention (anchor is the
*bottom-left* of the drawing area, y-up) so the tuned constants in pet_widget.py
carry over unchanged; the flip to Qt's y-down space happens once, in `_rect`.
"""

from __future__ import annotations

import math
import time
from enum import Enum, auto

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen

FILL_COLOR = QColor(0xF7, 0xF3, 0xEE)
OUTLINE_COLOR = QColor(0x2A, 0x1A, 0x16)


class EmoteKind(Enum):
    NONE = auto()
    THINKING = auto()
    THINKING_LONG = auto()
    SLEEP = auto()
    NOTIFY = auto()


class EmoteOverlay:
    """A small pixel-grid overlay (dots, "!") drawn above the pet's head.

    Stateless like JumpArc — derives its current frame from elapsed wall-clock
    time off the existing redraw loop, rather than owning its own timer. Draws
    procedurally at integer coordinates; never touches or resamples the body
    sprite image.
    """

    THINKING_FPS = 2.0
    THINKING_LONG_FPS = 0.8
    DOT_SIZE = 4.0
    DOT_SPACING = 8.0

    def __init__(self, canvas_height: float) -> None:
        self.kind = EmoteKind.NONE
        self._start_time = 0.0
        self._canvas_height = canvas_height

    def set_kind(self, new_kind: EmoteKind) -> None:
        if new_kind is self.kind:
            return
        self.kind = new_kind
        self._start_time = time.monotonic()

    def draw(self, painter: QPainter, anchor_x: float, anchor_y: float) -> None:
        """`anchor` is the bottom-left of the overlay's drawing area, in the same
        y-up space PetWidget expresses its sprite offsets in."""
        if self.kind is EmoteKind.THINKING:
            self._draw_thinking_dots(painter, anchor_x, anchor_y, self.THINKING_FPS)
        elif self.kind is EmoteKind.THINKING_LONG:
            self._draw_thinking_dots(painter, anchor_x, anchor_y, self.THINKING_LONG_FPS)
        elif self.kind is EmoteKind.NOTIFY:
            self._draw_alert_mark(painter, anchor_x, anchor_y)
        # NONE and SLEEP draw nothing.

    def _rect(self, x: float, mac_y: float, width: float, height: float) -> QRectF:
        """Convert a y-up, bottom-left-origin rect into Qt's y-down space."""
        return QRectF(round(x), round(self._canvas_height - mac_y - height), width, height)

    def _draw_thinking_dots(
        self, painter: QPainter, anchor_x: float, anchor_y: float, fps: float
    ) -> None:
        elapsed = time.monotonic() - self._start_time
        frame = int(elapsed * fps)
        visible_dots = (frame % 3) + 1

        for i in range(visible_dots):
            rect = self._rect(
                anchor_x + i * self.DOT_SPACING, anchor_y, self.DOT_SIZE, self.DOT_SIZE
            )
            self._fill_and_stroke(painter, rect)

    def _draw_alert_mark(self, painter: QPainter, anchor_x: float, anchor_y: float) -> None:
        """Pops in at t=0 (called exactly when the sprite's intro transition
        finishes) then bobs gently in place — the overlay is what keeps the held
        alert state from reading as frozen, since the sprite's own held frames
        barely differ."""
        elapsed = time.monotonic() - self._start_time
        bob_offset = round(math.sin(elapsed * 1.5) * 3)

        bar_width = 4.0
        bar_height = 10.0
        gap = 2.0
        dot_size = 4.0

        dot_y = anchor_y + bob_offset
        bar_y = dot_y + dot_size + gap

        dot_rect = self._rect(anchor_x, dot_y, dot_size, dot_size)
        bar_rect = self._rect(anchor_x, bar_y, bar_width, bar_height)

        self._fill_and_stroke(painter, dot_rect)
        self._fill_and_stroke(painter, bar_rect)

    @staticmethod
    def _fill_and_stroke(painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, FILL_COLOR)
        pen = QPen(OUTLINE_COLOR)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))
