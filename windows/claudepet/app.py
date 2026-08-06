"""Port of AppDelegate.swift — the composition root.

Wires the window, tray, pipe server, Cowork watcher and error detector together,
and maps incoming PetEvents onto pet reactions.
"""

from __future__ import annotations

import shutil
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, Qt, Signal

from . import paths, position_store
from .cowork_watcher import CoworkWatcher
from .error_detector import SessionErrorDetector
from .pet_event import PetEvent, PetEventKind
from .pet_window import PetWindow
from .pipe_server import PipeServer
from .tray import TrayController

DEFAULT_SLEEP_TIMEOUT = 5 * 60.0


class ClaudePetApp(QObject):
    """Cowork callbacks arrive on watchdog's thread; these signals carry them to
    the GUI thread, the same role `DispatchQueue.main.async` plays on macOS."""

    _cowork_prompt = Signal()
    _cowork_done = Signal(bool)
    _done_resolved = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._error_detector = SessionErrorDetector()

        install_petsend()

        sleep_timeout = position_store.load_sleep_timeout(DEFAULT_SLEEP_TIMEOUT)

        self.window = PetWindow()
        self.window.set_sleep_timeout(sleep_timeout)
        self.window.show()

        self._tray = TrayController(
            default_sleep_timeout=sleep_timeout,
            on_toggle_visibility=self.window.toggle_visibility,
            on_sleep_timeout_change=self._handle_sleep_timeout_change,
            on_quit=self._handle_quit,
        )
        self.window.on_right_click = self._handle_right_click

        self._pipe_server = PipeServer(self)
        self._pipe_server.event_received.connect(self._handle_event, Qt.ConnectionType.QueuedConnection)
        self._pipe_server.start()

        self._cowork_prompt.connect(self.window.set_thinking, Qt.ConnectionType.QueuedConnection)
        self._cowork_done.connect(self._handle_cowork_done, Qt.ConnectionType.QueuedConnection)
        self._done_resolved.connect(self._handle_cowork_done, Qt.ConnectionType.QueuedConnection)

        self._cowork_watcher = CoworkWatcher(
            watch_path=str(paths.cowork_sessions_dir()),
            on_prompt_sent=self._cowork_prompt.emit,
            on_done=self._cowork_done.emit,
        )
        self._cowork_watcher.start()

    # MARK: - Teardown

    def shutdown(self) -> None:
        self._cowork_watcher.stop()
        self._pipe_server.stop()

    # MARK: - Menu handlers

    def _handle_sleep_timeout_change(self, seconds: float) -> None:
        self.window.set_sleep_timeout(seconds)
        position_store.save_sleep_timeout(seconds)

    def _handle_right_click(self, global_pos: QPoint) -> None:
        self._tray.pop_up(global_pos)

    def _handle_quit(self) -> None:
        from PySide6.QtWidgets import QApplication

        self.shutdown()
        QApplication.quit()

    # MARK: - Events

    def _handle_event(self, event: PetEvent) -> None:
        if event.kind is PetEventKind.DONE:
            self._handle_done(event)
        elif event.kind is PetEventKind.PROMPT:
            if event.transcript_path:
                self._error_detector.note_prompt_start(event.transcript_path)
            self.window.set_thinking()
        elif event.kind is PetEventKind.TOOL:
            self.window.set_thinking()
        elif event.kind is PetEventKind.NOTIFY:
            self.window.trigger_alert()

    def _handle_done(self, event: PetEvent) -> None:
        path = event.transcript_path
        if not path:
            # No transcript info available (e.g. a hand-run `petsend done` with
            # no piped hook payload) — default to the success reaction.
            self.window.trigger_success()
            return

        # Scanning can touch a multi-MB file; keep it off the GUI thread so the
        # animation never stutters, then hop back via the signal.
        def scan() -> None:
            had_error = self._error_detector.had_error_since_prompt_start(path)
            self._done_resolved.emit(had_error)

        threading.Thread(target=scan, daemon=True).start()

    def _handle_cowork_done(self, had_error: bool) -> None:
        if had_error:
            self.window.trigger_fail()
        else:
            self.window.trigger_success()


def install_petsend() -> None:
    """Copies the bundled petsend out to its stable, hook-referenced path.

    Always overwrites rather than only installing once, so an app update also
    updates the CLI. Unlike macOS, Windows locks a running executable, so a
    concurrent hook invocation can make this fail — that's non-fatal, the
    existing copy keeps working and the next launch retries.
    """
    source = _bundled_petsend_dir()
    if source is None:
        return

    target_dir = paths.petsend_install_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target_dir, dirs_exist_ok=True)
    except (OSError, shutil.Error):
        pass


def _bundled_petsend_dir() -> Path | None:
    """Where build.ps1 places the petsend one-dir build inside the app."""
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).parent / "petsend"
    else:
        candidate = Path(__file__).resolve().parent.parent / "dist" / "petsend"
    return candidate if candidate.is_dir() else None
