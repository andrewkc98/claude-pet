"""Every Windows-specific path the app depends on, in one place.

The macOS app scatters `~/...` expansions across AppDelegate/SocketServer;
collecting them here means the petsend CLI and the app can't drift apart on the
pipe name, and the one empirically-risky path (Cowork's session directory) has a
single definition to correct if Claude Desktop ever moves it.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

APP_NAME = "ClaudePet"


def home_dir() -> Path:
    return Path(os.path.expanduser("~"))


def claudepet_dir() -> Path:
    """`%USERPROFILE%\\.claudepet` — mirrors macOS `~/.claudepet`."""
    return home_dir() / ".claudepet"


def petsend_install_dir() -> Path:
    return claudepet_dir() / "bin"


def petsend_exe_path() -> Path:
    return petsend_install_dir() / "petsend.exe"


def pipe_name() -> str:
    """The named pipe replacing macOS's AF_UNIX socket.

    Scoped by username so two users on one machine each get their own pet; the
    default DACL on a pipe created by a normal user already restricts access to
    that user, which is the security intent behind the macOS `chmod 0600`.
    """
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USERNAME", "default")
    safe = "".join(ch for ch in user if ch.isalnum() or ch in "-_") or "default"
    return rf"\\.\pipe\claudepet-{safe}"


def app_data_dir() -> Path:
    """`%APPDATA%`, with a sane fallback if the variable is missing."""
    raw = os.environ.get("APPDATA")
    if raw:
        return Path(raw)
    return home_dir() / "AppData" / "Roaming"


def state_dir() -> Path:
    """Where we persist pet position and settings (macOS uses UserDefaults)."""
    return app_data_dir() / APP_NAME


def state_file() -> Path:
    return state_dir() / "state.json"


def cowork_sessions_dir() -> Path:
    """Claude Desktop's Cowork session transcripts.

    Windows equivalent of macOS's
    `~/Library/Application Support/Claude/local-agent-mode-sessions`. Verified
    present with an identical internal layout:
    `<org>/<user>/local_<id>/.claude/projects/<slug>/<session>.jsonl`.
    """
    return app_data_dir() / "Claude" / "local-agent-mode-sessions"


def assets_dir() -> Path:
    """The sprite PNGs.

    Frozen (PyInstaller) builds get them next to the executable under `Assets`;
    running from source reads `../Assets` so the sprites stay single-sourced with
    the macOS app rather than duplicated into this folder.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "Assets"
    return Path(__file__).resolve().parent.parent.parent / "Assets"
