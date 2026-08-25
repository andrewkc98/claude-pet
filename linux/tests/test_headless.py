"""Headless checks for the logic that has no GUI dependency.

Run:  .venv/bin/python -m tests.test_headless      (from the linux/ dir)

Covers the two pieces most likely to break silently on a new platform: the
Cowork transcript tailing (including the must-not-replay-history rule) and the
transcript error scan.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claudepet.cowork_watcher import CoworkWatcher  # noqa: E402
from claudepet.error_detector import SessionErrorDetector  # noqa: E402

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        failures.append(label)


def append(path: str, obj: dict) -> None:
    # Compact separators matter: the real transcripts are written by
    # JSON.stringify, which emits `"is_error":true` with no space after the
    # colon, and the detectors match that exact byte sequence. Python's default
    # json.dumps would insert a space and silently defeat the check.
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, separators=(",", ":")) + "\n")


USER = {"type": "user", "message": {"role": "user", "content": "hi"}}
END_TURN = {"type": "assistant", "message": {"role": "assistant", "stop_reason": "end_turn"}}

# Shapes taken from real transcripts: a tool result is itself a role-"user"
# record carrying a tool_result block and a top-level toolUseResult key.
TOOL_ERROR = {
    "type": "user",
    "toolUseResult": {"stdout": "", "stderr": "boom"},
    "message": {
        "role": "user",
        "content": [{"type": "tool_result", "is_error": True, "content": "boom"}],
    },
}
TOOL_OK = {
    "type": "user",
    "toolUseResult": {"stdout": "fine", "stderr": ""},
    "message": {
        "role": "user",
        "content": [{"type": "tool_result", "is_error": False, "content": "fine"}],
    },
}


def test_cowork_watcher() -> None:
    print("CoworkWatcher")
    events: list[tuple[str, bool]] = []

    with tempfile.TemporaryDirectory() as tmp:
        transcript = os.path.join(tmp, "session.jsonl")

        # Pre-existing history that must NOT be replayed.
        append(transcript, USER)
        append(transcript, END_TURN)

        watcher = CoworkWatcher(
            watch_path=tmp,
            on_prompt_sent=lambda: events.append(("prompt", False)),
            on_done=lambda had_error: events.append(("done", had_error)),
        )
        watcher.start()
        time.sleep(0.5)

        # Touch the file so the watcher records its baseline offset.
        append(transcript, {"type": "system", "subtype": "init"})
        time.sleep(0.6)
        check(events == [], "pre-existing history is not replayed")

        # A clean turn.
        append(transcript, USER)
        time.sleep(0.4)
        append(transcript, END_TURN)
        time.sleep(0.6)
        check(("prompt", False) in events, "user record fires prompt")
        check(("done", False) in events, "end_turn fires done with no error")

        events.clear()

        # A turn containing a tool error.
        append(transcript, USER)
        time.sleep(0.3)
        append(transcript, TOOL_ERROR)
        time.sleep(0.3)
        append(transcript, END_TURN)
        time.sleep(0.6)
        check(("done", True) in events, "is_error marker makes the turn fail")
        check(
            events.count(("prompt", False)) == 1,
            "a tool result is not mistaken for a new prompt",
        )

        events.clear()

        # A successful tool call must not poison the turn.
        append(transcript, USER)
        time.sleep(0.3)
        append(transcript, TOOL_OK)
        time.sleep(0.3)
        append(transcript, END_TURN)
        time.sleep(0.6)
        check(("done", False) in events, "is_error:false does not trigger the fail path")

        events.clear()

        # The error flag must reset — the next clean turn is a success.
        append(transcript, USER)
        time.sleep(0.3)
        append(transcript, END_TURN)
        time.sleep(0.6)
        check(("done", False) in events, "error flag resets on the next prompt")
        check(("done", True) not in events, "stale error does not leak into next turn")

        # A `result` record is the second accepted completion shape.
        events.clear()
        append(transcript, {"type": "result", "subtype": "success"})
        time.sleep(0.6)
        check(("done", False) in events, "result record also counts as done")

        watcher.stop()


def test_error_detector() -> None:
    print("SessionErrorDetector")
    with tempfile.TemporaryDirectory() as tmp:
        transcript = os.path.join(tmp, "cli.jsonl")
        append(transcript, {"type": "assistant", "old": "history", "is_error": True})

        detector = SessionErrorDetector()
        detector.note_prompt_start(transcript)
        check(
            not detector.had_error_since_prompt_start(transcript),
            "error before the prompt start is ignored",
        )

        append(transcript, TOOL_ERROR)
        check(
            detector.had_error_since_prompt_start(transcript),
            "error after the prompt start is detected",
        )

        detector.note_prompt_start(transcript)
        append(transcript, {"type": "assistant", "message": {"stop_reason": "end_turn"}})
        check(
            not detector.had_error_since_prompt_start(transcript),
            "a new prompt start clears the previous error",
        )

        check(
            not detector.had_error_since_prompt_start(os.path.join(tmp, "missing.jsonl")),
            "missing transcript reports no error rather than raising",
        )


def main() -> int:
    test_cowork_watcher()
    test_error_detector()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
