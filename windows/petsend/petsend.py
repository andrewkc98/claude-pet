"""Windows port of Sources/petsend/main.swift.

Fire-and-forget: connect to the pet's named pipe, write one JSON line, exit 0.
Must never hang the caller (Claude Code hooks block on this), and must never fail
loudly if the pet app isn't running.

Usage:  petsend.exe <event> [source]
        event  = prompt | tool | done | notify   (default: done)
        source = free-form label                 (default: unknown)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

# Runs as a standalone executable, so it can't import the `claudepet` package;
# the pipe name is duplicated here deliberately, matching how the macOS build
# duplicates the socket path between the app and the CLI. Keep in sync with
# claudepet/paths.py:pipe_name().
_TIMEOUT_SECONDS = 0.2
_MAX_STDIN_BYTES = 65536


def pipe_name() -> str:
    import getpass

    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USERNAME", "default")
    safe = "".join(ch for ch in user if ch.isalnum() or ch in "-_") or "default"
    return rf"\\.\pipe\claudepet-{safe}"


def read_transcript_path_from_stdin() -> str | None:
    """Claude Code pipes the hook's JSON payload over stdin.

    We only care about `transcript_path`, forwarded so the pet can check the
    transcript for tool errors. Guarded by isatty so running `petsend` by hand
    from a terminal (no piped stdin) never blocks waiting on input.
    """
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return None
        raw = sys.stdin.buffer.read(_MAX_STDIN_BYTES)
    except Exception:
        return None

    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("transcript_path")
    return value if isinstance(value, str) else None


def send_event(event_type: str, source: str) -> None:
    transcript_path = read_transcript_path_from_stdin()

    message: dict[str, object] = {
        "event": event_type,
        "source": source,
        "ts": int(time.time()),
    }
    if transcript_path:
        message["transcript_path"] = transcript_path

    # Compact separators to match the byte-for-byte shape the macOS petsend emits.
    line = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

    # A Windows named pipe is openable with the plain builtin — no pywin32 needed
    # on the client side, which keeps this executable small and fast to start.
    try:
        with open(pipe_name(), "wb", buffering=0) as pipe:
            pipe.write(line)
    except OSError:
        # Pet isn't running, or the pipe is busy. Silence is the contract.
        pass


def main() -> None:
    event_type = sys.argv[1] if len(sys.argv) > 1 else "done"
    source = sys.argv[2] if len(sys.argv) > 2 else "unknown"

    worker = threading.Thread(target=send_event, args=(event_type, source), daemon=True)
    worker.start()
    worker.join(timeout=_TIMEOUT_SECONDS)

    # os._exit rather than sys.exit: skips interpreter teardown (and any blocked
    # daemon thread), which is the whole point — the hook must not wait on us.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
