"""Port of MenuBarController.swift, as a Linux system-tray icon.

Same menu contents as macOS: Show/Hide Pet, Sleep After, Launch at Login, Quit.
As on macOS, the pet's right-click reuses this exact QMenu instance rather than
building a second one, so checkbox states stay in sync between the two.

Icon note: macOS uses the `pawprint.fill` SF Symbol. There is no equivalent
system symbol on Linux, so the tray uses the cat's own idle frame — it renders
predictably at 16px without depending on an icon theme being installed.

**Tray availability note:** `QSystemTrayIcon` needs a StatusNotifierItem host
(or the older systray spec) provided by the desktop environment. KDE, XFCE,
Cinnamon and most others ship one; stock GNOME does not without an extension
such as "AppIndicator and KStatusNotifierItem Support". `__main__.py` checks
`QSystemTrayIcon.isSystemTrayAvailable()` at startup and refuses to run
without one rather than starting silently invisible.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import launch_at_login, paths
from .animation_config import FRAME_SIZE, IDLE

SLEEP_TIMEOUT_OPTIONS: list[tuple[str, float]] = [
    ("1 minute", 60),
    ("5 minutes", 5 * 60),
    ("15 minutes", 15 * 60),
    ("30 minutes", 30 * 60),
]


class TrayController:
    def __init__(
        self,
        default_sleep_timeout: float,
        on_toggle_visibility: Callable[[], None],
        on_sleep_timeout_change: Callable[[float], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_toggle_visibility = on_toggle_visibility
        self._on_sleep_timeout_change = on_sleep_timeout_change
        self._on_quit = on_quit
        self._selected_sleep_timeout = default_sleep_timeout

        self._menu = QMenu()
        self._tray = QSystemTrayIcon(_tray_icon())
        self._tray.setToolTip("ClaudePet")
        self._build_menu()
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._handle_activated)
        self._tray.show()

    def pop_up(self, global_pos: QPoint) -> None:
        """Shows the same menu instance used by the tray icon — right-clicking
        the pet itself, rather than requiring a trip to the tray."""
        self._menu.popup(global_pos)

    def _build_menu(self) -> None:
        toggle_action = QAction("Show/Hide Pet", self._menu)
        toggle_action.triggered.connect(lambda: self._on_toggle_visibility())
        self._menu.addAction(toggle_action)

        self._menu.addSeparator()

        sleep_menu = self._menu.addMenu("Sleep After")
        group = QActionGroup(self._menu)
        group.setExclusive(True)
        for title, seconds in SLEEP_TIMEOUT_OPTIONS:
            action = QAction(title, self._menu)
            action.setCheckable(True)
            action.setChecked(seconds == self._selected_sleep_timeout)
            action.triggered.connect(
                lambda _checked=False, value=seconds: self._handle_sleep_timeout_selected(value)
            )
            group.addAction(action)
            sleep_menu.addAction(action)

        self._menu.addSeparator()

        self._launch_action = QAction("Launch at Login", self._menu)
        self._launch_action.setCheckable(True)
        self._launch_action.setChecked(launch_at_login.is_enabled())
        self._launch_action.triggered.connect(self._handle_toggle_launch_at_login)
        self._menu.addAction(self._launch_action)

        self._menu.addSeparator()

        quit_action = QAction("Quit ClaudePet", self._menu)
        quit_action.triggered.connect(lambda: self._on_quit())
        self._menu.addAction(quit_action)

    def _handle_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason is QSystemTrayIcon.ActivationReason.Trigger:
            self._on_toggle_visibility()

    def _handle_sleep_timeout_selected(self, seconds: float) -> None:
        self._selected_sleep_timeout = seconds
        self._on_sleep_timeout_change(seconds)

    def _handle_toggle_launch_at_login(self) -> None:
        desired = not launch_at_login.is_enabled()
        actual = launch_at_login.set_enabled(desired)
        # Resync from disk rather than trusting the click: if the write
        # failed, the checkbox must not claim it succeeded.
        self._launch_action.setChecked(actual)


def _tray_icon() -> QIcon:
    sheet = QPixmap(str(paths.assets_dir() / f"{IDLE.resource_name}.png"))
    if sheet.isNull() or sheet.height() != FRAME_SIZE:
        return QIcon()
    frame = sheet.copy(0, 0, FRAME_SIZE, FRAME_SIZE)
    icon = QIcon()
    for size in (16, 24, 32, 48):
        icon.addPixmap(
            frame.scaled(
                size,
                size,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )
    return icon
