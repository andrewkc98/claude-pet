"""Port of CoworkWatcher.swift — Claude Desktop (Cowork) support.

Cowork doesn't honor ~/.claude/settings.json hooks: it spawns its own local
claude-code process with its own sandboxed HOME under
local-agent-mode-sessions/.../local_<id>/.claude/, so our Stop hook never fires
for it. Instead we watch its session transcript JSONL files for structured
turn-start/turn-completion records:
    {"type":"user", ...}                                 -> prompt sent (thinking)
    {"type":"assistant", message.stop_reason:"end_turn"} -> turn finished
    {"type":"result", ...}                               -> also treated as finished
      (seen in some audit.jsonl-style logs, kept as a second completion shape)

Success vs. failure is decided by scanning for a raw `"is_error":true` byte
marker in everything written since the last prompt — same technique as
SessionErrorDetector uses for the Claude Code CLI path, just tracked
incrementally here since this class already tails the file. We only ever inspect
`type`/`stop_reason` fields and this one fixed marker string; message content is
never read into memory beyond that, logged, or transmitted.

The macOS original uses FSEvents; here watchdog provides the same thing on top of
ReadDirectoryChangesW. The path is the Windows equivalent of
`~/Library/Application Support/Claude/local-agent-mode-sessions`, verified to
have an identical internal layout.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

ERROR_MARKER = b'"is_error":true'
MAX_LINE_LENGTH = 1_000_000


class CoworkWatcher:
    def __init__(
        self,
        watch_path: str,
        on_prompt_sent: Callable[[], None],
        on_done: Callable[[bool], None],
    ) -> None:
        self._watch_path = watch_path
        self._on_prompt_sent = on_prompt_sent
        self._on_done = on_done

        self._file_offsets: dict[str, int] = {}
        self._error_seen_since_prompt: dict[str, bool] = {}
        self._lock = threading.Lock()
        self._observer: Observer | None = None

    def start(self) -> None:
        if not os.path.isdir(self._watch_path):
            # Claude Desktop isn't installed, or has never run a Cowork session.
            # Nothing to watch; the Claude Code hook path still works.
            return

        handler = _JsonlChangeHandler(self._handle_changed_path)
        observer = Observer()
        try:
            observer.schedule(handler, self._watch_path, recursive=True)
            observer.start()
        except OSError:
            return
        self._observer = observer

    def stop(self) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=2.0)
        self._observer = None

    # MARK: - Internals

    def _handle_changed_path(self, path: str) -> None:
        if path.endswith(".jsonl"):
            self._check_for_events(path)

    def _check_for_events(self, path: str) -> None:
        try:
            file_size = os.path.getsize(path)
        except OSError:
            return

        with self._lock:
            previous_offset = self._file_offsets.get(path)
            if previous_offset is None:
                # First time seeing this file: start tracking from here, don't
                # replay history — otherwise a restart mid-session would fire a
                # burst of reactions for turns that already happened.
                self._file_offsets[path] = file_size
                return

        if file_size <= previous_offset:
            # Truncated or rewritten: resync rather than reading garbage.
            if file_size < previous_offset:
                with self._lock:
                    self._file_offsets[path] = file_size
            return

        try:
            with open(path, "rb") as handle:
                handle.seek(previous_offset)
                new_data = handle.read()
        except OSError:
            # claude-code may hold the transcript open with a restrictive share
            # mode. Skipping this notification is fine — the next write produces
            # another event, and the offset is unchanged so nothing is lost.
            return

        with self._lock:
            self._file_offsets[path] = previous_offset + len(new_data)

        for raw_line in new_data.split(b"\n"):
            if not raw_line or len(raw_line) >= MAX_LINE_LENGTH:
                continue
            self._process_line(path, raw_line)

    def _process_line(self, path: str, raw_line: bytes) -> None:
        if ERROR_MARKER in raw_line:
            with self._lock:
                self._error_seen_since_prompt[path] = True

        try:
            payload = json.loads(raw_line)
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(payload, dict):
            return

        record_type = payload.get("type")
        if not isinstance(record_type, str):
            return

        if record_type == "user":
            if _is_tool_result_record(payload):
                # Tool results come back as role-"user" records, so treating every
                # `type:"user"` line as a new prompt would reset the error flag on
                # the very line that just set it — the failure reaction could then
                # never fire. (The macOS CoworkWatcher has this bug; see
                # README-windows.md.) A tool result is mid-turn, not a new prompt.
                return
            with self._lock:
                self._error_seen_since_prompt[path] = False
            self._on_prompt_sent()
        elif _is_completion_record(record_type, payload):
            with self._lock:
                had_error = self._error_seen_since_prompt.get(path, False)
                self._error_seen_since_prompt[path] = False
            self._on_done(had_error)


def _is_tool_result_record(payload: dict) -> bool:
    """True for a role-"user" record that is really a tool result, not a prompt.

    Verified against real transcripts: these carry a top-level `toolUseResult`
    key and a `message.content` list containing a `tool_result` block, where a
    genuine prompt's content is a plain string or text blocks. Either signal is
    enough; both are checked so a change to one shape doesn't silently regress
    failure detection.
    """
    if "toolUseResult" in payload:
        return True
    message = payload.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return any(
        isinstance(block, dict) and block.get("type") == "tool_result" for block in content
    )


def _is_completion_record(record_type: str, payload: dict) -> bool:
    if record_type == "result":
        return True
    if record_type == "assistant":
        message = payload.get("message")
        if isinstance(message, dict) and message.get("stop_reason") == "end_turn":
            return True
    return False


class _JsonlChangeHandler(FileSystemEventHandler):
    """Funnels every watchdog event kind through one callback.

    FSEvents on macOS reports a flat list of changed paths regardless of the kind
    of change, so matching that here keeps the tailing logic identical.
    """

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = event.src_path
        if isinstance(path, bytes):
            path = path.decode("utf-8", "ignore")
        self._callback(path)
        dest = getattr(event, "dest_path", None)
        if dest:
            if isinstance(dest, bytes):
                dest = dest.decode("utf-8", "ignore")
            self._callback(dest)
