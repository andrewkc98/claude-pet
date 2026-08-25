"""Port of PetView.swift — the state machine and renderer.

Coordinate note: the macOS original works in AppKit's y-up, bottom-left-origin
space; Qt is y-down, top-left. Rather than flipping signs ad hoc at each call
site, all the tuned constants below stay in the macOS convention and the single
helper `_mac_to_qt_y` does the conversion. Vertical offsets remain "positive =
up" everywhere in this file.

One structural change from the original: PetView advanced its play-once states
as a side effect of `draw()`. Qt repaints for reasons of its own, so the frame is
resolved at the end of each tick and cached; `paintEvent` only blits.
"""

from __future__ import annotations

import time
from enum import Enum, auto
from typing import Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from . import animation_config as anim
from .emote_overlay import EmoteKind, EmoteOverlay
from .jump_arc import JumpArc
from .play_once_timer import PlayOnceTimer
from .sprite_sheet import SpriteSheet

SPRITE_DISPLAY_SIZE = 128
JUMP_HEADROOM = 32
WINDOW_WIDTH = SPRITE_DISPLAY_SIZE
WINDOW_HEIGHT = SPRITE_DISPLAY_SIZE + JUMP_HEADROOM

#: Anchors are bottom-left, in the y-up space the sprite occupies (y 0...128).
EMOTE_ANCHOR = (72.0, 96.0)
#: In the headroom above the 128pt sprite. Same x as the thinking-dots anchor —
#: that one's already tuned to sit over the head (cat faces right), just
#: projected up into the headroom.
ALERT_EMOTE_ANCHOR = (72.0, 132.0)

LONG_THINK_THRESHOLD = 120.0
ALERT_HOLD_FRAME_INTERVAL = 1.0
# Guarantees the alert stays visible at least this long even if the thing it was
# for resolves almost instantly (a fast permission prompt, a trailing hook from
# unrelated activity) — otherwise "real activity clears it" can mean it clears
# before anyone actually sees it.
MINIMUM_ALERT_VISIBLE_DURATION = 1.5


class State(Enum):
    IDLE = auto()
    THINKING = auto()
    JUMPING = auto()
    SLEEPING = auto()
    WAKING = auto()
    ALERTING = auto()
    SUCCEEDING = auto()
    FAILING = auto()


class AlertPhase(Enum):
    TRANSITIONING = auto()
    HELD = auto()


class PetWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(False)

        self.on_drag_ended: Callable[[QPoint], None] | None = None
        self.on_right_click: Callable[[QPoint], None] | None = None

        self._idle_sheet = SpriteSheet.load(anim.IDLE, SPRITE_DISPLAY_SIZE)
        self._jump_sheet = SpriteSheet.load(anim.JUMP, SPRITE_DISPLAY_SIZE)
        self._sleep_sheet = SpriteSheet.load(anim.SLEEP, SPRITE_DISPLAY_SIZE)
        self._wake_sheet = SpriteSheet.load(anim.WAKE, SPRITE_DISPLAY_SIZE)
        self._alert_sheet = SpriteSheet.load(anim.ALERT, SPRITE_DISPLAY_SIZE)
        self._success_sheet = SpriteSheet.load(anim.SUCCESS, SPRITE_DISPLAY_SIZE)
        self._fail_sheet = SpriteSheet.load(anim.FAIL, SPRITE_DISPLAY_SIZE)
        self._think_long_sheet = SpriteSheet.load(anim.THINK_LONG, SPRITE_DISPLAY_SIZE)

        self._frame_index = 0
        self._last_idle_frame_advance = 0.0
        self._last_sleep_frame_advance = 0.0
        self._last_think_long_frame_advance = 0.0
        self._thinking_start_time = 0.0
        self._is_currently_long_thinking = False

        self._jump_arc = JumpArc(anim.JUMP.duration or 0.7)
        self._wake_timer = PlayOnceTimer(anim.WAKE.duration or 0.6)
        self._alert_intro_timer = PlayOnceTimer(anim.ALERT.duration or 0.3)
        self._success_timer = PlayOnceTimer(anim.SUCCESS.duration or 0.7)
        self._fail_timer = PlayOnceTimer(anim.FAIL.duration or 0.7)
        self._emote_overlay = EmoteOverlay(canvas_height=WINDOW_HEIGHT)

        self._state = State.IDLE
        self._alert_phase = AlertPhase.TRANSITIONING
        self._alert_hold_start_time = 0.0
        self._alert_shown_at = 0.0

        self._last_activity_time = time.monotonic()
        self._sleep_timeout = 5 * 60.0

        self._drag_start_global = QPoint()
        self._drag_start_window = QPoint()
        self._is_dragging = False

        self._cached_frame: tuple[SpriteSheet | None, int, int] = (self._idle_sheet, 0, 0)

        self._animation_timer = QTimer(self)
        self._animation_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._animation_timer.timeout.connect(self._tick)
        self._animation_timer.start(int(1000 / anim.IDLE.fps))

    # MARK: - External triggers

    @property
    def _is_in_protected_reaction(self) -> bool:
        """States representing a brief, self-terminating reaction that should be
        allowed to finish playing rather than getting cut short by the next
        prompt/tool event — which, during an active turn, can arrive within
        milliseconds of the reaction starting.

        ALERTING is a special case, protected only for
        MINIMUM_ALERT_VISIBLE_DURATION: a genuine "needs you" alert should yield
        once real activity resumes (e.g. PostToolUse firing after an
        AskUserQuestion gets answered) rather than requiring a click even though
        the moment it was for has passed — but without a floor, a fast-resolving
        trigger could clear it before anyone actually perceives it. It persists
        during a true block regardless, since nothing else fires while blocked.
        """
        if self._state in (State.JUMPING, State.WAKING, State.SUCCEEDING, State.FAILING):
            return True
        if self._state is State.ALERTING:
            return (time.monotonic() - self._alert_shown_at) < MINIMUM_ALERT_VISIBLE_DURATION
        return False

    def set_thinking(self) -> None:
        if self._state is State.SLEEPING:
            self._begin_waking()
            return
        self._last_activity_time = time.monotonic()
        if self._is_in_protected_reaction:
            return
        if self._state is not State.THINKING:
            # Fresh entry into thinking — start the long-think clock. Repeated
            # calls while already thinking (e.g. one per tool call) must NOT
            # reset this, or a long task never actually reaches the threshold.
            self._thinking_start_time = time.monotonic()
            self._is_currently_long_thinking = False
        self._set_state(State.THINKING)
        # Re-assert whichever overlay is currently correct rather than always
        # THINKING — this fires on every tool call, so blindly resetting it would
        # flip long-think's slow dots back to fast on the next call.
        self._emote_overlay.set_kind(
            EmoteKind.THINKING_LONG if self._is_currently_long_thinking else EmoteKind.THINKING
        )

    def trigger_jump(self) -> None:
        if self._state is State.SLEEPING:
            self._begin_waking()
            return
        self._last_activity_time = time.monotonic()
        if self._is_in_protected_reaction:
            return
        self._set_state(State.JUMPING)
        self._emote_overlay.set_kind(EmoteKind.NONE)
        self._jump_arc.trigger()

    def note_activity(self) -> None:
        """For events with no dedicated visual yet: still counts as activity for
        the sleep timer, and still wakes the pet if it's asleep."""
        if self._state is State.SLEEPING:
            self._begin_waking()
            return
        self._last_activity_time = time.monotonic()

    def trigger_alert(self) -> None:
        """An alert blocks other visuals until acknowledged (clicked). Plays the
        frames-1-2-3 transition once, then holds on frames 3/4 with the overlay
        supplying the visual interest until dismissed."""
        if self._state is State.SLEEPING:
            self._begin_waking()
            return
        self._last_activity_time = time.monotonic()
        if self._state is State.WAKING:
            return
        self._set_state(State.ALERTING)
        self._alert_phase = AlertPhase.TRANSITIONING
        self._alert_shown_at = time.monotonic()
        self._emote_overlay.set_kind(EmoteKind.NONE)
        self._alert_intro_timer.trigger()

    def trigger_success(self) -> None:
        """The done-reaction for a turn that completed with no tool errors."""
        if self._state is State.SLEEPING:
            self._begin_waking()
            return
        self._last_activity_time = time.monotonic()
        if self._is_in_protected_reaction:
            return
        self._set_state(State.SUCCEEDING)
        self._emote_overlay.set_kind(EmoteKind.NONE)
        self._success_timer.trigger()

    def trigger_fail(self) -> None:
        """The done-reaction for a turn where at least one tool call errored."""
        if self._state is State.SLEEPING:
            self._begin_waking()
            return
        self._last_activity_time = time.monotonic()
        if self._is_in_protected_reaction:
            return
        self._set_state(State.FAILING)
        self._emote_overlay.set_kind(EmoteKind.NONE)
        self._fail_timer.trigger()

    def set_sleep_timeout(self, seconds: float) -> None:
        self._sleep_timeout = seconds

    # MARK: - State machine

    def _set_state(self, new_state: State) -> None:
        if new_state is self._state:
            return
        self._state = new_state
        self._frame_index = 0
        now = time.monotonic()
        self._last_idle_frame_advance = now
        self._last_sleep_frame_advance = now

    def _begin_waking(self) -> None:
        self._set_state(State.WAKING)
        self._emote_overlay.set_kind(EmoteKind.NONE)
        self._wake_timer.trigger()
        self._last_activity_time = time.monotonic()

    def _check_sleep_timeout(self) -> None:
        if self._state is not State.IDLE:
            return
        if (time.monotonic() - self._last_activity_time) < self._sleep_timeout:
            return
        self._set_state(State.SLEEPING)
        self._emote_overlay.set_kind(EmoteKind.NONE)

    # MARK: - Animation loop

    def _tick(self) -> None:
        self._check_sleep_timeout()

        now = time.monotonic()
        if self._state is State.IDLE:
            self._frame_index, self._last_idle_frame_advance = self._advance_frame_if_due(
                self._idle_sheet, anim.IDLE.fps, self._last_idle_frame_advance, now
            )
        elif self._state is State.THINKING:
            self._tick_thinking(now)
        elif self._state is State.SLEEPING:
            self._frame_index, self._last_sleep_frame_advance = self._advance_frame_if_due(
                self._sleep_sheet, anim.SLEEP.fps, self._last_sleep_frame_advance, now
            )
        # Play-once states derive their frame from elapsed progress in
        # _resolve_frame(), not from the tick.

        self._cached_frame = self._resolve_frame()
        self.update()

    def _tick_thinking(self, now: float) -> None:
        long_now = (now - self._thinking_start_time) >= LONG_THINK_THRESHOLD
        if long_now != self._is_currently_long_thinking:
            self._is_currently_long_thinking = long_now
            self._frame_index = 0
            self._last_idle_frame_advance = now
            self._last_think_long_frame_advance = now
            self._emote_overlay.set_kind(
                EmoteKind.THINKING_LONG if long_now else EmoteKind.THINKING
            )

        if long_now:
            self._frame_index, self._last_think_long_frame_advance = self._advance_frame_if_due(
                self._think_long_sheet,
                anim.THINK_LONG.fps,
                self._last_think_long_frame_advance,
                now,
            )
        else:
            self._frame_index, self._last_idle_frame_advance = self._advance_frame_if_due(
                self._idle_sheet, anim.IDLE.fps, self._last_idle_frame_advance, now
            )

    def _advance_frame_if_due(
        self, sheet: SpriteSheet | None, fps: float, last_advance: float, now: float
    ) -> tuple[int, float]:
        """The master timer ticks at idle's rate (fast enough for smooth arcs and
        overlays in other states), but each looping sheet only advances its own
        frame at its own configured fps — otherwise sleep would play at idle's
        rate, which was a real bug in an earlier version of the macOS app."""
        if not sheet or fps <= 0:
            return self._frame_index, last_advance
        frame_duration = 1.0 / fps
        if (now - last_advance) < frame_duration:
            return self._frame_index, last_advance
        return (self._frame_index + 1) % len(sheet), now

    # MARK: - Painting

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        sheet, draw_frame_index, vertical_offset = self._cached_frame
        if not sheet:
            # Same loud failure mode as the macOS original: a red block means the
            # sprite assets didn't load, rather than an invisible no-op.
            painter.fillRect(self.rect(), QColor(255, 59, 48))
            return

        clamped_index = min(max(draw_frame_index, 0), len(sheet) - 1)
        pixmap: QPixmap = sheet.frames[clamped_index]

        # Sprite sits at the bottom of the window in the macOS y-up space, so in
        # Qt it starts JUMP_HEADROOM down — and a positive (upward) jump offset
        # subtracts.
        top = WINDOW_HEIGHT - SPRITE_DISPLAY_SIZE - vertical_offset
        painter.drawPixmap(0, top, pixmap)

        base_anchor = ALERT_EMOTE_ANCHOR if self._state is State.ALERTING else EMOTE_ANCHOR
        self._emote_overlay.draw(painter, base_anchor[0], base_anchor[1] + vertical_offset)

    def _resolve_frame(self) -> tuple[SpriteSheet | None, int, int]:
        """Resolves (sheet, frame index, vertical offset) for the current state,
        and advances play-once states (jumping/waking/alerting/...) as a side
        effect. Called from the tick, never from paintEvent."""
        if self._state is State.IDLE:
            return self._idle_sheet, self._frame_index, 0

        if self._state is State.THINKING:
            sheet = self._think_long_sheet if self._is_currently_long_thinking else self._idle_sheet
            return sheet, self._frame_index, 0

        if self._state is State.SLEEPING:
            return self._sleep_sheet, self._frame_index, 0

        if self._state is State.JUMPING:
            offset = self._jump_arc.current_offset()
            progress = self._jump_arc.progress()
            if not self._jump_arc.is_active:
                self._set_state(State.IDLE)
            return self._jump_sheet, _progress_index(progress, self._jump_sheet), offset

        if self._state is State.WAKING:
            progress = self._wake_timer.progress()
            if not self._wake_timer.is_active:
                self._set_state(State.IDLE)
            return self._wake_sheet, _progress_index(progress, self._wake_sheet), 0

        if self._state is State.ALERTING:
            return self._alert_sheet, self._alert_frame_index(), 0

        if self._state is State.SUCCEEDING:
            progress = self._success_timer.progress()
            if not self._success_timer.is_active:
                self._set_state(State.IDLE)
            return self._success_sheet, _progress_index(progress, self._success_sheet), 0

        if self._state is State.FAILING:
            progress = self._fail_timer.progress()
            if not self._fail_timer.is_active:
                self._set_state(State.IDLE)
            return self._fail_sheet, _progress_index(progress, self._fail_sheet), 0

        return self._idle_sheet, self._frame_index, 0

    def _alert_frame_index(self) -> int:
        count = len(self._alert_sheet) if self._alert_sheet else 4
        if self._alert_phase is AlertPhase.TRANSITIONING:
            progress = self._alert_intro_timer.progress()
            if not self._alert_intro_timer.is_active:
                self._alert_phase = AlertPhase.HELD
                self._alert_hold_start_time = time.monotonic()
                # Pop-in, right as the transition ends.
                self._emote_overlay.set_kind(EmoteKind.NOTIFY)
            return min(int(progress * 3), 2)

        elapsed = time.monotonic() - self._alert_hold_start_time
        toggled = int(elapsed / ALERT_HOLD_FRAME_INTERVAL) % 2 == 0
        return min(2, count - 1) if toggled else min(3, count - 1)

    # MARK: - Mouse

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """A click wakes the pet if it's asleep (handled inside trigger_jump's own
        sleeping check); any other click jumps — including one that clears an
        active alert, since trigger_jump already transitions cleanly out of
        ALERTING the same way real activity does."""
        if event.button() is Qt.MouseButton.LeftButton:
            self.trigger_jump()
            window = self.window()
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_window = window.frameGeometry().topLeft()
            self._is_dragging = True
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._is_dragging:
            return
        delta = event.globalPosition().toPoint() - self._drag_start_global
        self.window().move(self._drag_start_window + delta)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() is not Qt.MouseButton.LeftButton or not self._is_dragging:
            return
        self._is_dragging = False
        if self.on_drag_ended:
            self.on_drag_ended(self.window().frameGeometry().topLeft())
        event.accept()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if self.on_right_click:
            self.on_right_click(event.globalPos())
        event.accept()


def _progress_index(progress: float, sheet: SpriteSheet | None) -> int:
    count = len(sheet) if sheet else 1
    return min(int(progress * count), count - 1)
