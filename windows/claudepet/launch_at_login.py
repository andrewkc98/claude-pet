"""Port of LaunchAtLogin.swift.

macOS uses SMAppService; the Windows equivalent with the same "no admin rights,
no scheduled task" property is a value under HKCU's Run key. Writing there is a
per-user change and is removed cleanly by toggling the menu item back off.
"""

from __future__ import annotations

import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ClaudePet"


def _launch_command() -> str:
    """The command Windows should run at login.

    Frozen builds point at the executable directly; running from source has to go
    back through the interpreter with `-m claudepet`.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m claudepet'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Returns the resulting state, so callers can resync a checkbox on failure."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_WRITE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        return is_enabled()
    return enabled
