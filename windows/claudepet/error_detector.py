"""Port of SessionErrorDetector.swift."""

from __future__ import annotations

import os
import threading

ERROR_MARKER = b'"is_error":true'

# Deliberately small: this is only used when we never saw this turn's prompt
# start (e.g. the pet was launched or relaunched mid-turn). A generous window
# here risks false-flagging a stale error from several messages back in a
# long-running conversation as belonging to the current turn — confirmed in
# testing with a multi-MB transcript.
MAX_SCAN_BYTES = 200_000


class SessionErrorDetector:
    """Detects whether a Claude Code CLI turn ended with any tool error.

    PostToolUse hooks simply don't fire when a tool call errors (confirmed
    empirically — a failing Bash command and a Read on a nonexistent file both
    produced zero PostToolUse invocations). The local session transcript is the
    only reliable signal: every tool_result content block carries
    `"is_error":true/false`, so we snapshot the transcript's byte offset at the
    start of each prompt and, on Stop, scan everything written since for that
    marker. A plain byte-substring search rather than JSON parsing, consistent
    with treating this content as untrusted — we only ever check for a fixed
    marker string, never parse or execute anything from it.
    """

    def __init__(self) -> None:
        self._prompt_start_offsets: dict[str, int] = {}
        self._lock = threading.Lock()

    def note_prompt_start(self, transcript_path: str) -> None:
        size = _file_size(transcript_path)
        if size is None:
            return
        with self._lock:
            self._prompt_start_offsets[transcript_path] = size

    def had_error_since_prompt_start(self, transcript_path: str) -> bool:
        """True if the marker appears in anything written since the last prompt.

        Falls back to scanning the last MAX_SCAN_BYTES if we never saw a prompt
        start (e.g. first turn after app launch), rather than replaying the file.
        """
        with self._lock:
            start_offset = self._prompt_start_offsets.get(transcript_path)

        current_size = _file_size(transcript_path)
        if current_size is None:
            return False

        if start_offset is None:
            offset = max(0, current_size - MAX_SCAN_BYTES)
        else:
            offset = start_offset

        if current_size <= offset:
            return False

        try:
            with open(transcript_path, "rb") as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError:
            # The transcript may be momentarily locked by the writing process;
            # a missed error reading is better than crashing the reaction path.
            return False

        return ERROR_MARKER in data


def _file_size(path: str) -> int | None:
    try:
        return os.path.getsize(path)
    except OSError:
        return None
