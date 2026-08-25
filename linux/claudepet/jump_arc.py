"""Port of JumpArc.swift."""

from __future__ import annotations

import math

from .play_once_timer import PlayOnceTimer

PEAK_HEIGHT = 24


class JumpArc:
    """Produces an eased, integer-pixel vertical offset for a jump bounce.

    Deliberately knows nothing about sprites/frames — sprite selection during a
    jump is driven separately (by PetWidget, off `progress()`), not by this.
    """

    def __init__(self, duration: float) -> None:
        self._timer = PlayOnceTimer(duration)

    @property
    def is_active(self) -> bool:
        return self._timer.is_active

    def trigger(self) -> None:
        self._timer.trigger()

    def progress(self) -> float:
        """0...1 progress through the jump, for driving frame selection."""
        return self._timer.progress()

    def current_offset(self) -> int:
        """Vertical offset in points, 0 at ground level, positive = up.

        Always an integer so the sprite stays aligned to the pixel grid. Callers
        must *subtract* this from a top-left y coordinate — Qt is y-down; see the
        coordinate note in pet_widget.py.
        """
        if not self._timer.is_active:
            return 0
        t = self._timer.progress()
        eased = math.sin(t * math.pi)
        return int(round(eased * PEAK_HEIGHT))
