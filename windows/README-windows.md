# ClaudePet for Windows

The Windows port of ClaudePet — the same pixel cat, reacting to both **Claude Code** and
**Claude Desktop's Cowork mode**.

**Requirements:** Windows 10 1809 or later, and [Claude Code](https://claude.com/claude-code)
and/or Claude Desktop.

The macOS app is in [`../Sources/ClaudePet`](../Sources/ClaudePet); this folder is a
separate app shell in Python + PySide6 that reuses the same sprite assets and the same
event protocol. The state machine, animation timings and transcript-tailing logic are
ports of the Swift originals.

## Install

1. Download `ClaudePet-windows.zip` from the Releases page, unzip it anywhere (e.g.
   `%LOCALAPPDATA%\Programs\ClaudePet`), and run `ClaudePet.exe`.

2. **SmartScreen will warn on first launch.** This app isn't code-signed (a certificate
   costs money), so Windows shows "Windows protected your PC". This is expected for free
   independent software, not a sign anything is wrong. Click **More info** → **Run anyway**.
   You only need to do this once.

3. A cat icon appears in your system tray. The cat itself shows up floating over your
   other windows — drag it anywhere you like; its position is remembered across restarts.

4. **Claude Desktop / Cowork needs no setup.** Once ClaudePet is running, it detects Cowork
   activity automatically. Skip to step 6 if you don't use Claude Code.

5. **Wire it up to Claude Code.** Create or edit `%USERPROFILE%\.claude\settings.json`:

   ```bash
   notepad %USERPROFILE%\.claude\settings.json
   ```

   and merge in the block below, **replacing `<you>` with your Windows username**:

   ```json
   {
     "hooks": {
       "UserPromptSubmit": [
         {"hooks": [{"type": "command", "command": "C:/Users/<you>/.claudepet/bin/petsend.exe prompt claude-code"}]}
       ],
       "PostToolUse": [
         {"matcher": "*", "hooks": [{"type": "command", "command": "C:/Users/<you>/.claudepet/bin/petsend.exe tool claude-code"}]}
       ],
       "Stop": [
         {"hooks": [{"type": "command", "command": "C:/Users/<you>/.claudepet/bin/petsend.exe done claude-code"}]}
       ],
       "Notification": [
         {"hooks": [{"type": "command", "command": "C:/Users/<you>/.claudepet/bin/petsend.exe notify claude-code"}]}
       ],
       "PreToolUse": [
         {"matcher": "AskUserQuestion", "hooks": [{"type": "command", "command": "C:/Users/<you>/.claudepet/bin/petsend.exe notify claude-code"}]}
       ]
     }
   }
   ```

   Use **absolute paths with forward slashes**, as shown. `%USERPROFILE%` is not
   reliably expanded inside hook commands.

   > **Do not use backslashes here, even doubled.** Claude Code runs hook commands
   > through **bash**, not `cmd.exe`. Bash treats `\` as an escape character, so a
   > JSON `"C:\\Users\\you\\.claudepet\\bin\\petsend.exe"` reaches bash as
   > `C:\Users\you\...` and is unescaped again into `C:Usersyou.claudepetbinpetsend.exe`
   > — every hook then fails with exit 127 `command not found`. The failure is silent
   > from the pet's point of view (it simply never receives an event), so it looks
   > like broken IPC rather than a broken path. Forward slashes survive both layers.
   > If Claude Code events aren't reaching the pet, check your session transcript
   > under `%USERPROFILE%\.claude\projects\` for `"hookErrors"`.

   `petsend.exe` is installed to `%USERPROFILE%\.claudepet\bin\` automatically the first
   time you launch `ClaudePet.exe`, so this step just needs the JSON above.

   **If you already have hooks configured**, merge these entries into your existing `hooks`
   object rather than replacing the file.

   **Note on the "!" alert:** as on macOS, it only fires for `AskUserQuestion` (Claude
   explicitly asking you something) — not for tool-permission prompts, which don't go
   through the `Notification` hook.

6. Restart any running Claude Code sessions (hooks are read at session start) and try a
   prompt — the cat should show thinking dots, then react when the turn finishes.

## Tray / right-click options

Click the tray icon, or right-click the cat itself, for:
- **Show/Hide Pet**
- **Sleep After** — how long without activity before it falls asleep (1/5/15/30 min)
- **Launch at Login**
- **Quit ClaudePet**

Click the cat to wake it (if asleep) or make it jump. A blocked/alert state clears itself
once you respond, or you can click to dismiss it early.

## Uninstall

1. Toggle **Launch at Login** off (removes the `ClaudePet` value under
   `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
2. Quit ClaudePet from the tray menu.
3. Delete the folder you unzipped.
4. Delete `%USERPROFILE%\.claudepet\` and `%APPDATA%\ClaudePet\`.
5. Remove the hook entries from `%USERPROFILE%\.claude\settings.json`.

## Building from source

Requires Python 3.12+.

```bash
python -m venv .venv
```

```bash
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```bash
.\build.ps1 -Clean
```

The build lands in `dist\ClaudePet\`, with `petsend` nested inside it. To run without
packaging: `.\.venv\Scripts\python.exe -m claudepet` from this directory.

Run the headless logic checks with:

```bash
.\.venv\Scripts\python.exe -m tests.test_headless
```

## How it differs from the macOS version

| Concern | macOS | Windows |
|---|---|---|
| Window | `NSPanel`, borderless/non-activating/floating | Layered `Qt.Tool` window: `WS_EX_LAYERED\|TOPMOST\|TOOLWINDOW\|NOACTIVATE` |
| Menu | `NSStatusItem` in the menu bar | `QSystemTrayIcon` in the notification area |
| IPC | AF_UNIX socket `~/.claudepet/pet.sock`, chmod 0600 | Named pipe `\\.\pipe\claudepet-<user>` |
| Cowork transcripts | `~/Library/Application Support/Claude/local-agent-mode-sessions` | `%APPDATA%\Claude\local-agent-mode-sessions` (same internal layout) |
| File watching | FSEvents | `ReadDirectoryChangesW`, via `watchdog` |
| Launch at login | `SMAppService` | `HKCU\...\CurrentVersion\Run` |
| Settings | `UserDefaults` | `%APPDATA%\ClaudePet\state.json` |
| Single instance | Implicit in `.app` launch | `Local\ClaudePet-<user>` named mutex |
| Tray icon | `pawprint.fill` SF Symbol | The cat's own idle frame (no equivalent system symbol) |

The wire protocol is identical, so the only per-platform difference in the hook block is
the path to `petsend`.

### One behavioural fix, not present in the macOS version

The macOS `CoworkWatcher` treats every `{"type":"user"}` transcript record as "a new prompt
was sent" and resets its error flag there. But tool results come back as role-`user`
records too, and those are exactly the records carrying `"is_error":true` — so the flag is
set and cleared by the same line, and the Cowork failure reaction can never fire.

The Windows port skips records that carry a `tool_result` block or a top-level
`toolUseResult` key, so a failed tool call during a Cowork turn produces the fail
animation. See `_is_tool_result_record` in
[`claudepet/cowork_watcher.py`](claudepet/cowork_watcher.py). The same fix would apply to
[`../Sources/ClaudePet/CoworkWatcher.swift`](../Sources/ClaudePet/CoworkWatcher.swift:136).

### Known limitations

- **Fractional display scaling.** Sprites are verified crisp and correctly sized at 100%
  and 150%. At 125% and 175% a fractional scale factor means source pixels can't map to a
  whole number of screen pixels, so edges may look slightly uneven. Pixel art, not a
  rendering bug. (The app declares per-monitor DPI awareness v2 explicitly at startup —
  see `_declare_dpi_awareness` in [`claudepet/__main__.py`](claudepet/__main__.py) — because
  the PyInstaller bootloader's manifest only declares v1, under which the packaged build
  would render the pet at two-thirds size on a scaled display.)
- **`petsend.exe` startup.** It's a one-dir PyInstaller build specifically to avoid
  one-file's ~1s self-extraction on every tool call. It still costs more than the macOS
  native binary; it never blocks Claude Code regardless, because it gives up after 200 ms.
- Not code-signed, so SmartScreen warns on first run. No auto-updater and no installer.
