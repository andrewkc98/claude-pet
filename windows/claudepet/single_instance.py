"""Prevent a second ClaudePet from running for the same user.

macOS gets this for free — relaunching a `.app` just activates the running copy.
On Windows, double-clicking the exe twice starts two independent processes, and
because the pipe server is created with PIPE_UNLIMITED_INSTANCES both would
register listeners under the same name: hook events would then go to whichever
instance happened to accept first, and two cats would sit on top of each other.

A named mutex is the standard Windows answer. It's scoped to the session with the
`Local\\` prefix, so two different users signed into the same machine each get
their own pet.
"""

from __future__ import annotations

import ctypes
import getpass
import os

ERROR_ALREADY_EXISTS = 183

#: Held for the lifetime of the process; released by the kernel on exit, so a
#: crash can't leave a stale lock behind.
_mutex_handle = None


def _mutex_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USERNAME", "default")
    safe = "".join(ch for ch in user if ch.isalnum() or ch in "-_") or "default"
    return f"Local\\ClaudePet-{safe}"


def acquire() -> bool:
    """True if this process is the only instance; False if one already runs."""
    global _mutex_handle
    try:
        # use_last_error routes GetLastError through ctypes' own per-call capture,
        # so an unrelated ctypes call can't clobber it between CreateMutexW and
        # the check below.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, _mutex_name())
        last_error = ctypes.get_last_error()
    except (AttributeError, OSError):
        # Can't check — better to run than to refuse to start.
        return True

    if not handle:
        return True
    if last_error == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return False
    _mutex_handle = handle
    return True
