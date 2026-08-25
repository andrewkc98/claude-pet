"""Entry point. Port of AppMain.swift."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from . import single_instance
from .app import ClaudePetApp


def main() -> int:
    if not single_instance.acquire():
        # Already running. Exit quietly rather than adding a second cat and a
        # second socket listener competing for the same hook events.
        return 0

    # Pixel art: let Qt hand us real device pixels on a scaled display instead
    # of rounding the scale factor and resampling the sprites into mush. (No
    # DPI-manifest step is needed here the way Windows needs one — X11/Wayland
    # report scale factors to Qt directly, with no separate awareness opt-in.)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ClaudePet")
    # The pet and the tray are the whole UI; closing the window must not quit.
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None,
            "ClaudePet",
            "No system tray is available on this desktop, so ClaudePet can't show its menu. "
            "On GNOME, install an extension such as \"AppIndicator and KStatusNotifierItem "
            "Support\" and try again.",
        )
        return 1

    pet = ClaudePetApp()
    app.aboutToQuit.connect(pet.shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
