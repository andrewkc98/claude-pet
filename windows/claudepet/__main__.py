"""Entry point. Port of AppMain.swift."""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from . import single_instance
from .app import ClaudePetApp

#: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def _declare_dpi_awareness() -> None:
    """Opt into per-monitor DPI awareness v2 before Qt reads the screen DPI.

    Pixel art needs the real device pixel ratio: at anything less than
    per-monitor awareness Windows reports 96 DPI and then bitmap-scales the
    window, which blurs the sprites on a scaled display.

    In practice both supported launch paths already declare this via a manifest —
    python.exe's own manifest in dev, and ClaudePet.manifest (embedded by
    build.ps1) in the packaged build — and manifest-declared awareness is latched
    before any Python runs, so this call is normally a harmless no-op. It's kept
    as a fallback for launches that bypass both, e.g. an embedded interpreter or
    a PyInstaller build made without the custom manifest.
    """
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(_PER_MONITOR_AWARE_V2)
    except (AttributeError, OSError):
        # Pre-1703 Windows: fall back to the older, coarser API.
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def main() -> int:
    _declare_dpi_awareness()

    if not single_instance.acquire():
        # Already running. Exit quietly rather than adding a second cat and a
        # second pipe listener competing for the same hook events.
        return 0

    # Pixel art: let Qt hand us real device pixels on 125%/150% displays instead
    # of rounding the scale factor and resampling the sprites into mush.
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
            "No system tray is available on this desktop, so ClaudePet can't show its menu.",
        )
        return 1

    pet = ClaudePetApp()
    app.aboutToQuit.connect(pet.shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
