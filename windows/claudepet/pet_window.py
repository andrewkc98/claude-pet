"""Port of PetPanel.swift — the borderless, transparent, always-on-top window.

Flag mapping from the macOS original:
  .borderless          -> FramelessWindowHint
  .nonactivatingPanel  -> WindowDoesNotAcceptFocus + WA_ShowWithoutActivating
  level = .floating    -> WindowStaysOnTopHint
  LSUIElement          -> Qt.Tool (no taskbar button, no Alt-Tab entry)

macOS's `collectionBehavior` has no Windows analogue (there are no Spaces), and
`beginActivity` isn't needed — Windows doesn't App-Nap timers.

`WindowStaysOnTopHint` alone is not sufficient here. Qt sets WS_EX_TOPMOST as a
*style bit* when the flags are applied, but that does not by itself place the
window into the topmost z-band — and the two can disagree. Observed in practice:
the pet carried WS_EX_TOPMOST while sitting at z-index 8 with six ordinary
windows stacked above it, so the flag read as correct while the cat was buried.
The band has to be claimed explicitly with SetWindowPos(HWND_TOPMOST), which
needs a live HWND and therefore can only happen after the window is shown.

It also has to be re-asserted: other applications claim the topmost band when
they go fullscreen or show their own overlays, and Explorer restarts drop it
entirely. A cheap periodic nudge (SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE moves
nothing and steals no focus) is what keeps the cat reliably on top.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from . import position_store
from .pet_widget import WINDOW_HEIGHT, WINDOW_WIDTH, PetWidget

#: SetWindowPos hwndInsertAfter / flags. See MSDN SetWindowPos.
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010

#: How often to re-claim the topmost band. Long enough to be free, short enough
#: that a fullscreen app which stole it doesn't hide the cat for noticeably long.
_TOPMOST_KEEPALIVE_MS = 2000


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

        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(_TOPMOST_KEEPALIVE_MS)
        self._topmost_timer.timeout.connect(self._assert_topmost)

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

    # MARK: - Always-on-top

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        # First point at which winId() is a real HWND, so this is the earliest
        # the topmost band can actually be claimed.
        self._assert_topmost()
        self._topmost_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().hideEvent(event)
        self._topmost_timer.stop()

    def _assert_topmost(self) -> None:
        """Claim the topmost z-band. No-op off Windows; never raises."""
        if sys.platform != "win32":
            return
        hwnd = int(self.winId())
        if not hwnd:
            return
        try:
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                _HWND_TOPMOST,
                0,
                0,
                0,
                0,
                _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE,
            )
        except OSError:
            # Losing the band is cosmetic; it is never worth taking the app down.
            pass

    # MARK: - Internals

    def _handle_right_click(self, global_pos: QPoint) -> None:
        if self.on_right_click:
            self.on_right_click(global_pos)

    def _persist_position(self, top_left: QPoint) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        position_store.save_position(top_left, screen)
