"""Port of PetEvent.swift — the wire format shared with the macOS app.

Keeping this identical is what lets the same Claude Code hook block work on both
platforms with only the command path changed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum


class PetEventKind(str, Enum):
    PROMPT = "prompt"
    TOOL = "tool"
    DONE = "done"
    NOTIFY = "notify"


@dataclass(frozen=True)
class PetEvent:
    kind: PetEventKind
    source: str | None
    #: Path to the local Claude Code session transcript, when petsend was able to
    #: read one off the hook's stdin payload. Used to detect success/failure for
    #: DONE by scanning for is_error markers — PostToolUse hooks simply don't fire
    #: when a tool call errors, so the transcript is the only reliable signal.
    transcript_path: str | None

    @staticmethod
    def decode(raw: bytes) -> "PetEvent | None":
        """Parse one newline-delimited JSON event, or None if unrecognised.

        Unknown `event` values are dropped rather than raising: this data arrives
        over an IPC channel and is treated as untrusted input.
        """
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(payload, dict):
            return None

        event = payload.get("event")
        if not isinstance(event, str):
            return None
        try:
            kind = PetEventKind(event)
        except ValueError:
            return None

        source = payload.get("source")
        transcript_path = payload.get("transcript_path")
        return PetEvent(
            kind=kind,
            source=source if isinstance(source, str) else None,
            transcript_path=transcript_path if isinstance(transcript_path, str) else None,
        )
