"""Port of PetPanel.swift — the borderless, transparent, always-on-top window.

Flag mapping from the macOS original:
  .borderless          -> FramelessWindowHint
  .nonactivatingPanel  -> WindowDoesNotAcceptFocus + WA_ShowWithoutActivating
  level = .floating    -> WindowStaysOnTopHint
  LSUIElement          -> Qt.Tool (no taskbar button, no Alt-Tab entry)

macOS's `collectionBehavior` has no Windows analogue (there are no Spaces), and
`beginActivity` isn't needed — Windows doesn't App-Nap timers.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from . import position_store
from .pet_widget import WINDOW_HEIGHT, WINDOW_WIDTH, PetWidget


class PetWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._pet = PetWidget(self)
        self._pet.move(0, 0)
        self._pet.on_drag_ended = self._persist_position

        self.on_right_click: Callable[[QPoint], None] | None = None
        self._pet.on_right_click = self._handle_right_click

        restored = position_store.load_position(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.move(restored or position_store.default_position(WINDOW_WIDTH, WINDOW_HEIGHT))

    # MARK: - Façade, mirroring PetPanel's forwarding methods

    def set_thinking(self) -> None:
        self._pet.set_thinking()

    def trigger_jump(self) -> None:
        self._pet.trigger_jump()

    def note_activity(self) -> None:
        self._pet.note_activity()

    def trigger_alert(self) -> None:
        self._pet.trigger_alert()

    def trigger_success(self) -> None:
        self._pet.trigger_success()

    def trigger_fail(self) -> None:
        self._pet.trigger_fail()

    def set_sleep_timeout(self, seconds: float) -> None:
        self._pet.set_sleep_timeout(seconds)

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()

    # MARK: - Internals

    def _handle_right_click(self, global_pos: QPoint) -> None:
        if self.on_right_click:
            self.on_right_click(global_pos)

    def _persist_position(self, top_left: QPoint) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        position_store.save_position(top_left, screen)
