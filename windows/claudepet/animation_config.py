"""Sprite animation descriptors. Direct port of SpriteAnimationConfig.swift.

Values here are tuned, not arbitrary — `fps` of 0 means the animation's frame is
derived from elapsed-time progress against `duration` instead of ticked, and
`alert`'s duration covers only the intro transition (the held state alternates
frames separately, in PetWidget).
"""

from __future__ import annotations

from dataclasses import dataclass

FRAME_SIZE = 64


@dataclass(frozen=True)
class SpriteAnimationConfig:
    resource_name: str
    frame_size: int
    #: Frame-advance rate for looping animations (idle, sleep).
    fps: float
    loops: bool
    #: Total playback time for non-looping animations (jump, wake).
    #: Frame index is derived from elapsed-time progress, not `fps`.
    duration: float | None


IDLE = SpriteAnimationConfig("cat_idle", FRAME_SIZE, 7, True, None)
JUMP = SpriteAnimationConfig("cat_jump", FRAME_SIZE, 0, False, 0.9)
SLEEP = SpriteAnimationConfig("cat_sleep_v2_calm", FRAME_SIZE, 1.5, True, None)
WAKE = SpriteAnimationConfig("cat_wake", FRAME_SIZE, 0, False, 0.6)

#: duration covers only the frames-1-2-3 transition into the held state;
#: the held alternation between frames 3/4 is driven separately in PetWidget.
ALERT = SpriteAnimationConfig("cat_alert", FRAME_SIZE, 0, False, 0.3)

SUCCESS = SpriteAnimationConfig("cat_success", FRAME_SIZE, 0, False, 1.5)
FAIL = SpriteAnimationConfig("cat_fail", FRAME_SIZE, 0, False, 1.5)

#: Presentation swap for thinking past LONG_THINK_THRESHOLD (see PetWidget) —
#: curled/settled pose instead of idle's stance, at a calmer pace.
THINK_LONG = SpriteAnimationConfig("cat_think_long", FRAME_SIZE, 1, True, None)

ALL = (IDLE, JUMP, SLEEP, WAKE, ALERT, SUCCESS, FAIL, THINK_LONG)
