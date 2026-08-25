"""Every Linux-specific path the app depends on, in one place.

Mirrors windows/claudepet/paths.py, which mirrors the same scattered `~/...`
expansions in the macOS AppDelegate/SocketServer — collecting them here means
petsend and the app can't drift apart on the socket path, and the one
empirically-unverifiable path (Cowork's session directory; there's no official
Claude Desktop build for Linux) has a single definition to correct later.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ClaudePet"


def home_dir() -> Path:
    return Path(os.path.expanduser("~"))


def claudepet_dir() -> Path:
    """`~/.claudepet` — identical to the macOS path; this is a POSIX platform too."""
    return home_dir() / ".claudepet"


def petsend_install_dir() -> Path:
    return claudepet_dir() / "bin"


def petsend_exe_path() -> Path:
    """No `.exe` suffix on Linux; matches the macOS binary name."""
    return petsend_install_dir() / "petsend"


def socket_path() -> Path:
    """AF_UNIX socket, chmod 0600 by the server — identical scheme to macOS's
    `~/.claudepet/pet.sock`. Unlike Windows' named pipe, no per-user scoping in
    the name is needed: the socket is a file under this user's own home
    directory, so two users on one machine already get separate sockets."""
    return claudepet_dir() / "pet.sock"


def _xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME")
    if raw:
        return Path(raw)
    return home_dir() / ".config"


def state_dir() -> Path:
    """Where we persist pet position and settings (macOS uses UserDefaults)."""
    return _xdg_config_home() / APP_NAME


def state_file() -> Path:
    return state_dir() / "state.json"


def autostart_dir() -> Path:
    return _xdg_config_home() / "autostart"


def autostart_desktop_file() -> Path:
    return autostart_dir() / "claudepet.desktop"


def _xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME")
    if raw:
        return Path(raw)
    return home_dir() / ".local" / "share"


def cowork_sessions_dir() -> Path:
    """Claude Desktop's Cowork session transcripts, if it's ever installed here.

    Best-effort guess at the Linux equivalent of macOS's
    `~/Library/Application Support/Claude/local-agent-mode-sessions` — there is
    no official Claude Desktop build for Linux to verify this against, unlike
    the Windows path (`%APPDATA%\\Claude\\...`), which was confirmed against a
    real install. `CoworkWatcher.start()` no-ops cleanly if this directory
    doesn't exist, so getting it wrong here costs nothing beyond Cowork
    detection simply staying inactive; the Claude Code hook path is unaffected
    either way. Checked under XDG data first (where Electron apps on Linux
    typically keep `userData`), falling back to XDG config.
    """
    data_candidate = _xdg_data_home() / "Claude" / "local-agent-mode-sessions"
    if data_candidate.is_dir():
        return data_candidate
    return _xdg_config_home() / "Claude" / "local-agent-mode-sessions"


def assets_dir() -> Path:
    """The sprite PNGs.

    Frozen (PyInstaller) builds get them next to the executable under `Assets`;
    running from source reads `../Assets` so the sprites stay single-sourced
    with the macOS and Windows apps rather than duplicated into this folder.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "Assets"
    return Path(__file__).resolve().parent.parent.parent / "Assets"
