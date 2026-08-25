"""Port of PlayOnceTimer.swift."""

from __future__ import annotations

import time


class PlayOnceTimer:
    """Elapsed-time-based progress for a one-shot animation.

    Stateless aside from a start time — matches JumpArc/EmoteOverlay's pattern of
    deriving state from wall-clock time off the existing redraw loop rather than
    owning a timer of its own.
    """

    def __init__(self, duration: float) -> None:
        self.duration = duration
        self.is_active = False
        self._start_time = 0.0

    def trigger(self) -> None:
        self._start_time = time.monotonic()
        self.is_active = True

    def progress(self) -> float:
        """0...1 progress through the duration.

        Returns 1 once finished, and flips `is_active` false the first time that
        happens — callers rely on that edge to transition out of the state.
        """
        if not self.is_active:
            return 1.0
        elapsed = time.monotonic() - self._start_time
        if elapsed >= self.duration:
            self.is_active = False
            return 1.0
        return elapsed / self.duration
