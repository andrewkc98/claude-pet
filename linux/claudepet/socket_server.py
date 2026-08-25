"""Port of SocketServer.swift, using the same AF_UNIX scheme macOS does.

Listens on `~/.claudepet/pet.sock`, chmod'd 0600 so only this user can connect
— the same intent as the macOS original, achieved the same POSIX way (Windows
approximates it with a named pipe's default security descriptor instead; see
windows/claudepet/pipe_server.py). No payload is ever executed and unknown
event names are dropped (see PetEvent.decode).

Each accepted connection is handed to a short-lived thread so a slow writer
can't block the next hook invocation — Claude Code fires these on every tool
call.
"""

from __future__ import annotations

import os
import socket
import threading

from PySide6.QtCore import QObject, Signal

from . import paths
from .pet_event import PetEvent

#: Matches the macOS 4 KiB per-line cap.
MAX_MESSAGE_BYTES = 4096
_RECV_CHUNK = 4096
_BACKLOG = 16


class SocketServer(QObject):
    """Listens on the pet's Unix domain socket and re-emits decoded events.

    `event_received` is emitted from a worker thread; connect it with a queued
    connection (the default across threads in Qt) so handlers run on the GUI
    thread, mirroring the macOS `DispatchQueue.main.async` hop.
    """

    event_received = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._socket_path = paths.socket_path()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._listener: socket.socket | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        listener = self._bind()
        if listener is None:
            return
        self._listener = listener
        self._thread = threading.Thread(target=self._serve_forever, args=(listener,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._listener is not None:
            try:
                self._listener.close()
            except OSError:
                pass
        try:
            self._socket_path.unlink()
        except OSError:
            pass

    # MARK: - Internals

    def _bind(self) -> socket.socket | None:
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        # A stale socket file from a crashed previous run must not block bind.
        # single_instance already guarantees we're the only live app, so
        # whatever is at this path can't have a listener behind it.
        try:
            self._socket_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            return None

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self._socket_path))
            os.chmod(self._socket_path, 0o600)
            listener.listen(_BACKLOG)
        except OSError:
            listener.close()
            return None
        return listener

    def _serve_forever(self, listener: socket.socket) -> None:
        while not self._stopping.is_set():
            try:
                connection, _ = listener.accept()
            except OSError:
                return  # Listener closed by stop().
            worker = threading.Thread(target=self._handle_client, args=(connection,), daemon=True)
            worker.start()

    def _handle_client(self, connection: socket.socket) -> None:
        buffer = bytearray()
        try:
            connection.settimeout(2.0)
            while len(buffer) < MAX_MESSAGE_BYTES:
                try:
                    chunk = connection.recv(_RECV_CHUNK)
                except OSError:
                    break  # Client closed, or the socket timed out. Both are normal.
                if not chunk:
                    break
                buffer.extend(chunk)
                if b"\n" in buffer:
                    break
        finally:
            try:
                connection.close()
            except OSError:
                pass

        self._dispatch(bytes(buffer))

    def _dispatch(self, raw: bytes) -> None:
        line, _, _ = raw.partition(b"\n")
        line = line.strip()
        if not line or len(line) > MAX_MESSAGE_BYTES:
            return
        event = PetEvent.decode(line)
        if event is not None:
            self.event_received.emit(event)
