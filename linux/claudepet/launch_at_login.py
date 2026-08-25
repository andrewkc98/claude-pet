"""Port of LaunchAtLogin.swift.

macOS uses SMAppService; Windows uses the HKCU Run key. The Linux equivalent
with the same "no admin rights, no system service" property is the XDG
autostart spec: a `.desktop` file under `~/.config/autostart/`, picked up by
every major desktop environment (GNOME, KDE, XFCE, Cinnamon, ...) at login.
Writing it is a per-user change and is removed cleanly by toggling the menu
item back off.
"""

from __future__ import annotations

import sys

from . import paths

_DESKTOP_ENTRY_TEMPLATE = """[Desktop Entry]
Type=Application
Name=ClaudePet
Comment=A pixel-art cat that reacts to Claude Code and Cowork
Exec={command}
Icon=claudepet
Terminal=false
X-GNOME-Autostart-enabled=true
"""


def _launch_command() -> str:
    """The command to run at login.

    Frozen builds point at the executable directly; running from source has to
    go back through the interpreter with `-m claudepet`.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m claudepet'


def is_enabled() -> bool:
    return paths.autostart_desktop_file().is_file()


def set_enabled(enabled: bool) -> bool:
    """Returns the resulting state, so callers can resync a checkbox on failure."""
    target = paths.autostart_desktop_file()
    try:
        if enabled:
            paths.autostart_dir().mkdir(parents=True, exist_ok=True)
            target.write_text(
                _DESKTOP_ENTRY_TEMPLATE.format(command=_launch_command()), encoding="utf-8"
            )
        else:
            target.unlink(missing_ok=True)
    except OSError:
        return is_enabled()
    return enabled
