# ClaudePet for Linux

The Linux port of ClaudePet — the same pixel cat, reacting to both **Claude Code** and,
where available, **Claude Desktop's Cowork mode**.

**Requirements:** X11 or Wayland with a system tray host (see [Tray availability](#tray--right-click-options)
below), and [Claude Code](https://claude.com/claude-code).

The macOS app is in [`../Sources/ClaudePet`](../Sources/ClaudePet); the Windows app is in
[`../windows`](../windows). This folder is a third shell in the same Python + PySide6 stack
as the Windows port — it reuses the same sprite assets and the same event protocol, and most
of its modules (the state machine, animation timings, transcript-tailing logic) are simply
the Windows port's files, unmodified. Only the platform-facing pieces differ: IPC, window
top-most handling, launch-at-login, and single-instance locking.

## Install

There's no prebuilt release yet — build from source (below), or run directly with Python.

## Wire it up to Claude Code

1. Create or edit `~/.claude/settings.json`:

   ```bash
   ${EDITOR:-nano} ~/.claude/settings.json
   ```

   and merge in:

   ```json
   {
     "hooks": {
       "UserPromptSubmit": [
         {"hooks": [{"type": "command", "command": "~/.claudepet/bin/petsend prompt claude-code"}]}
       ],
       "PostToolUse": [
         {"matcher": "*", "hooks": [{"type": "command", "command": "~/.claudepet/bin/petsend tool claude-code"}]}
       ],
       "Stop": [
         {"hooks": [{"type": "command", "command": "~/.claudepet/bin/petsend done claude-code"}]}
       ],
       "Notification": [
         {"hooks": [{"type": "command", "command": "~/.claudepet/bin/petsend notify claude-code"}]}
       ],
       "PreToolUse": [
         {"matcher": "AskUserQuestion", "hooks": [{"type": "command", "command": "~/.claudepet/bin/petsend notify claude-code"}]}
       ]
     }
   }
   ```

   `~/.claudepet/bin/petsend` is installed automatically the first time you launch the app, so
   this step just needs the JSON above; nothing else to build or copy.

   **If you already have hooks configured**, merge these entries into your existing `hooks`
   object rather than replacing the file.

   **Note on the "!" alert:** as on macOS and Windows, it only fires for `AskUserQuestion`
   (Claude explicitly asking you something) — not for tool-permission prompts, which don't go
   through the `Notification` hook.

2. Restart any running Claude Code sessions (hooks are read at session start) and try a
   prompt — the cat should show thinking dots, then react when the turn finishes.

**Cowork:** there's no official Claude Desktop build for Linux at the time of writing, so this
is forward-looking rather than verified. `claudepet/paths.py:cowork_sessions_dir()` guesses at
where an Electron-based Claude Desktop would keep its session transcripts on Linux; if that
guess is wrong (or nothing is installed there), the watcher just finds no directory and stays
inactive — Cowork detection failing costs nothing and doesn't affect the Claude Code hook path.

## Tray / right-click options

Click the tray icon, or right-click the cat itself, for:
- **Show/Hide Pet**
- **Sleep After** — how long without activity before it falls asleep (1/5/15/30 min)
- **Launch at Login**
- **Quit ClaudePet**

Click the cat to wake it (if asleep) or make it jump. A blocked/alert state clears itself
once you respond, or you can click to dismiss it early.

**Tray availability:** the tray icon needs a StatusNotifierItem host (or the older XEmbed
systray spec), which KDE, XFCE, Cinnamon, MATE, and most other desktops provide out of the
box. Stock GNOME does **not** ship one — install an extension such as
["AppIndicator and KStatusNotifierItem Support"](https://extensions.gnome.org/extension/615/appindicator-support/)
first. The app checks `QSystemTrayIcon.isSystemTrayAvailable()` at launch and refuses to start
with a clear message rather than running invisibly if no tray host is present.

## Uninstall

1. If you enabled Launch at Login, toggle it off first (tray or right-click menu), while the
   app is still running — this deletes `~/.config/autostart/claudepet.desktop` cleanly.
2. Quit ClaudePet (tray menu, or right-click the cat → Quit).
3. Delete wherever you unzipped/built the app.
4. Delete `~/.claudepet/` (the socket dir and installed `petsend`) and `~/.config/ClaudePet/`
   (saved position and settings).
5. Remove the hook entries you added to `~/.claude/settings.json`.

## Building from source

Requires Python 3.12+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./build.sh --clean
```

The build lands in `dist/ClaudePet/`, with `petsend` nested inside it. To run without
packaging: `.venv/bin/python -m claudepet` from this directory.

Run the headless logic checks with:

```bash
.venv/bin/python -m tests.test_headless
```

To add an application-menu entry (separate from the auto-generated autostart entry, which
"Launch at Login" manages for you), copy [`claudepet.desktop`](claudepet.desktop) to
`~/.local/share/applications/`, pointing `Exec=` at your built `dist/ClaudePet/ClaudePet`.

## How it differs from the macOS and Windows versions

| Concern | macOS | Windows | Linux |
|---|---|---|---|
| Window | `NSPanel`, borderless/non-activating/floating | Layered `Qt.Tool` window, kept topmost by a periodic `SetWindowPos` re-assert | `Qt.Tool` window with `WindowStaysOnTopHint`; the WM/compositor owns the topmost band, nothing further to reassert |
| Menu | `NSStatusItem` in the menu bar | `QSystemTrayIcon` in the notification area | `QSystemTrayIcon` via StatusNotifierItem/XEmbed (needs a tray host; absent on stock GNOME) |
| IPC | AF_UNIX socket `~/.claudepet/pet.sock`, chmod 0600 | Named pipe `\\.\pipe\claudepet-<user>` | AF_UNIX socket `~/.claudepet/pet.sock`, chmod 0600 — identical scheme to macOS |
| Cowork transcripts | `~/Library/Application Support/Claude/local-agent-mode-sessions` (verified) | `%APPDATA%\Claude\local-agent-mode-sessions` (verified) | `~/.local/share/Claude/local-agent-mode-sessions` or `~/.config/Claude/...` (**best-effort guess** — no official Linux build to verify against) |
| File watching | FSEvents | `ReadDirectoryChangesW`, via `watchdog` | inotify, via `watchdog` |
| Launch at login | `SMAppService` | `HKCU\...\CurrentVersion\Run` | XDG autostart `.desktop` file in `~/.config/autostart/` |
| Settings | `UserDefaults` | `%APPDATA%\ClaudePet\state.json` | `~/.config/ClaudePet/state.json` (XDG, respects `$XDG_CONFIG_HOME`) |
| Single instance | Implicit in `.app` launch | `Local\ClaudePet-<user>` named mutex | `flock()` on `~/.claudepet/claudepet.lock` |
| Tray icon | `pawprint.fill` SF Symbol | The cat's own idle frame | The cat's own idle frame |

The wire protocol is identical across all three platforms, so the only per-platform
difference in the hook block is the path to `petsend`.

### Known limitations

- **No official Cowork verification.** See the Cowork section above — the watch path is an
  educated guess, safe to be wrong, unverified against a real install.
- **Wayland positioning.** Dragging works (the app tracks pointer deltas locally), but plain
  Wayland gives clients no protocol to query or restore an absolute global screen position, so
  "remember where I left it" across restarts may not work on every compositor. Verified on X11.
- **Tray host required.** See [Tray availability](#tray--right-click-options) — the app refuses
  to start rather than run with an invisible menu if none is present.
- **No installer or auto-updater**, same as the other two platforms currently.
