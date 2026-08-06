"""Port of SpriteSheet.swift — horizontal strip PNG to a list of frames.

Frames are pre-scaled once at load time with nearest-neighbour, rather than
scaled on every paint: these are 64x64 pixel-art cells drawn at 128, and any
smoothing turns them to mush.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from . import paths
from .animation_config import SpriteAnimationConfig


class SpriteSheet:
    """The frames of one animation, already scaled to display size."""

    def __init__(self, frames: list[QPixmap]) -> None:
        self.frames = frames

    def __bool__(self) -> bool:
        return bool(self.frames)

    def __len__(self) -> int:
        return len(self.frames)

    @classmethod
    def load(cls, config: SpriteAnimationConfig, display_size: int) -> "SpriteSheet | None":
        url = paths.assets_dir() / f"{config.resource_name}.png"
        image = QPixmap(str(url))
        if image.isNull():
            return None

        frame_width = config.frame_size
        frame_height = config.frame_size
        if frame_width <= 0:
            return None
        if image.height() != frame_height or image.width() % frame_width != 0:
            return None

        frame_count = image.width() // frame_width
        frames: list[QPixmap] = []
        for i in range(frame_count):
            cropped = image.copy(i * frame_width, 0, frame_width, frame_height)
            if cropped.isNull():
                continue
            scaled = cropped.scaled(
                display_size,
                display_size,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            frames.append(scaled)

        if not frames:
            return None
        return cls(frames)
