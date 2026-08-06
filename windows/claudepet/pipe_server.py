"""Port of SocketServer.swift, using a Windows named pipe.

macOS uses an AF_UNIX socket at `~/.claudepet/pet.sock` chmod'd 0600. The
Windows equivalent is a named pipe; it gets the process token's default security
descriptor, which grants access to the creating user, SYSTEM and administrators
— close to the 0600 intent, and adequate here since the only thing a local
process could do by writing to it is make a cartoon cat jump. No payload is ever
executed and unknown event names are dropped (see PetEvent.decode).

Unlike the macOS accept loop, which handles one client at a time, each accepted
connection is handed to a short-lived thread so a slow writer can't block the
next hook invocation — Claude Code fires these on every tool call.
"""

from __future__ import annotations

import threading

import pywintypes
import win32file
import win32pipe
from PySide6.QtCore import QObject, Signal

from . import paths
from .pet_event import PetEvent

#: Matches the macOS 4 KiB per-line cap.
MAX_MESSAGE_BYTES = 4096
_BUFFER_SIZE = 4096


class PipeServer(QObject):
    """Listens on the pet's named pipe and re-emits decoded events.

    `event_received` is emitted from a worker thread; connect it with a queued
    connection (the default across threads in Qt) so handlers run on the GUI
    thread, mirroring the macOS `DispatchQueue.main.async` hop.
    """

    event_received = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pipe_name = paths.pipe_name()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()

    # MARK: - Internals

    def _serve_forever(self) -> None:
        while not self._stopping.is_set():
            handle = self._create_instance()
            if handle is None:
                # Creation failing usually means something transient (another
                # instance racing us at startup); back off rather than spin.
                if self._stopping.wait(1.0):
                    return
                continue

            try:
                win32pipe.ConnectNamedPipe(handle, None)
            except pywintypes.error:
                _close(handle)
                continue

            if self._stopping.is_set():
                _close(handle)
                return

            worker = threading.Thread(target=self._handle_client, args=(handle,), daemon=True)
            worker.start()

    def _create_instance(self):
        try:
            return win32pipe.CreateNamedPipe(
                self._pipe_name,
                win32pipe.PIPE_ACCESS_INBOUND,
                win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                _BUFFER_SIZE,
                _BUFFER_SIZE,
                0,
                None,
            )
        except pywintypes.error:
            return None

    def _handle_client(self, handle) -> None:
        buffer = bytearray()
        try:
            while len(buffer) < MAX_MESSAGE_BYTES:
                try:
                    code, chunk = win32file.ReadFile(handle, _BUFFER_SIZE)
                except pywintypes.error:
                    break  # Client closed, or broke the pipe. Both are normal.
                if not chunk:
                    break
                buffer.extend(chunk)
                if b"\n" in buffer:
                    break
        finally:
            try:
                win32pipe.DisconnectNamedPipe(handle)
            except pywintypes.error:
                pass
            _close(handle)

        self._dispatch(bytes(buffer))

    def _dispatch(self, raw: bytes) -> None:
        line, _, _ = raw.partition(b"\n")
        line = line.strip()
        if not line or len(line) > MAX_MESSAGE_BYTES:
            return
        event = PetEvent.decode(line)
        if event is not None:
            self.event_received.emit(event)


def _close(handle) -> None:
    try:
        win32file.CloseHandle(handle)
    except pywintypes.error:
        pass
