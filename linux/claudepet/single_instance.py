"""Prevent a second ClaudePet from running for the same user.

macOS gets this for free — relaunching a `.app` just activates the running
copy. On Linux, running the binary twice starts two independent processes,
and both would try to bind the same AF_UNIX socket path: the second bind
would either fail or (since socket_server.py unlinks a stale socket file
before binding) steal the path out from under the first, leaving one of the
two pets deaf to every hook event.

An flock'd lock file is the standard POSIX answer, and — unlike a Windows
named mutex, which the kernel releases automatically on process exit — the
same is true here: flock is released the moment the holding process's file
descriptors close, including on a crash or SIGKILL, so a stale lock can never
outlive its process.
"""

from __future__ import annotations

import fcntl

from . import paths

#: Held for the lifetime of the process; the kernel releases it when this
#: process's file descriptors close, so a crash can't leave a stale lock.
_lock_file = None


def acquire() -> bool:
    """True if this process is the only instance; False if one already runs."""
    global _lock_file

    paths.claudepet_dir().mkdir(parents=True, exist_ok=True)
    lock_path = paths.claudepet_dir() / "claudepet.lock"

    try:
        handle = open(lock_path, "w")
    except OSError:
        # Can't even open the lock file — better to run than to refuse to start.
        return True

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # Already locked by a running instance.
        handle.close()
        return False

    _lock_file = handle  # Keep the descriptor alive; closing it drops the lock.
    return True
