# Desktop Pet for Claude — Build Plan (macOS, M4)

**Stack:** Swift + SwiftUI (native, LSUIElement app)
**Art:** sprite sheets (pixel pet)
**Transport:** Unix domain socket, pet app is the server

---

## 1. Architecture

```
┌──────────────────────────────────────────┐
│  EMITTERS (many)                         │
│  1. Claude Code hooks  ──┐               │
│  2. Cowork/Desktop app  ─┼─► petsend ────┼──► ~/.claudepet/pet.sock
│  3. Chrome ext (claude.ai)┘  (tiny CLI)  │         │
└──────────────────────────────────────────┘         │
                                                     ▼
                                    ┌────────────────────────────────┐
                                    │  PetApp.app (Swift, no Dock)   │
                                    │  • SocketServer (listener)     │
                                    │  • PetState machine            │
                                    │  • SpriteView (NSPanel)        │
                                    │  • MenuBarExtra (settings)     │
                                    └────────────────────────────────┘
```

**Why a socket instead of a file:** event-driven, zero polling, sub-ms latency, and the
emitter blocks for ~1ms instead of Claude Code waiting on disk I/O. A file/FIFO works too
but you'd be polling or juggling FSEvents.

### Event protocol (newline-delimited JSON, one event per line)

```json
{"event":"prompt","source":"claude-code","session":"abc123","ts":1754400000}
{"event":"done","source":"claude-code","session":"abc123","ts":1754400012}
{"event":"tool","source":"claude-code","tool":"Bash","ts":1754400005}
{"event":"notify","source":"claude-code","message":"needs permission","ts":...}
```

Keep it dumb and additive. New emitters = new `source` values, no app changes.

---

## 2. Component breakdown

### A. PetApp (Swift/SwiftUI)

| Piece | Implementation notes |
|---|---|
| Window | `NSPanel` with `styleMask: [.borderless, .nonactivatingPanel]`, `isOpaque = false`, `backgroundColor = .clear`, `level = .floating`, `collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]` |
| No Dock icon | `LSUIElement = YES` in Info.plist (or `NSApp.setActivationPolicy(.accessory)`) |
| Drag to place | Override `mouseDragged` on the content view → `panel.setFrameOrigin`. Save to `UserDefaults` on `mouseUp` |
| Menu bar | `MenuBarExtra` (SwiftUI, macOS 13+): toggle visibility, sleep timeout slider, scale, quit |
| Sprites | One PNG sheet per animation. `NSImage` → crop rect per frame. Set `interpolation = .none` so pixel art stays crisp on Retina |
| Animation loop | `Timer.publish` at 10–12 fps driving a frame index. Set `Timer.tolerance` and disable App Nap (see gotchas) |
| Launch at login | `SMAppService.mainApp.register()` (macOS 13+). One line, no login-item hacks |

### B. State machine

```
       prompt / tool
IDLE ──────────────► THINKING ──done──► JUMP ──(anim ends)──► IDLE
  │                      │                                      │
  └──── no events for N min ──────────────────────────────────► SLEEP
                                                                 │
SLEEP ──any event OR click──► WAKE (stretch anim) ──────────► IDLE
```

- `N` default 5 min, configurable in menu bar.
- Reset the sleep timer on *any* inbound event and on any click/drag.
- Debounce JUMP: if 3 `done` events land in 2s, play once. Otherwise it looks broken.

### C. Sprite assets (5 animations, 64×64 frames)

| Animation | Frames | Loop |
|---|---|---|
| idle | 4–6 (breathing, occasional blink) | yes |
| thinking | 4 (head bob / spinner) | yes |
| jump | 6–8 (anticipate → launch → hang → land squash) | no |
| sleep | 2–4 (Zzz float) | yes |
| wake | 4 (stretch) | no |

Sources: Aseprite ($20, best tool), or free CC0 sheets on itch.io / OpenGameArt, or generate
with an image model and clean up. **Lock the frame size and sheet layout before you write the
loader** — retrofitting a different layout is the #1 time sink here.

### D. Emitters

**1. Claude Code hooks** — global config, `~/.claude/settings.json`. This is what's actually
installed, not just the original sketch — kept in sync here since the live file lives outside
this repo and would otherwise be silently lost on a fresh machine or a settings reset:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks":[{"type":"command","command":"~/.claudepet/bin/petsend prompt claude-code"}]}],
    "PostToolUse":      [{"matcher":"*","hooks":[{"type":"command","command":"~/.claudepet/bin/petsend tool claude-code"}]}],
    "Stop":             [{"hooks":[{"type":"command","command":"~/.claudepet/bin/petsend done claude-code"}]}],
    "Notification":     [{"hooks":[{"type":"command","command":"~/.claudepet/bin/petsend notify claude-code"}]}],
    "PreToolUse":       [{"matcher":"AskUserQuestion","hooks":[{"type":"command","command":"~/.claudepet/bin/petsend notify claude-code"}]}]
  }
}
```

`petsend` is built and copied to `~/.claudepet/bin/petsend` (see project.yml's `petsend` target) —
hooks reference that stable path, not the ephemeral Xcode DerivedData build output.

**Why `PreToolUse` too:** `Notification` alone covers genuine permission prompts and idle-timeout
nudges, but empirically does *not* fire for `AskUserQuestion` — confirmed by dumping hook payloads
with no piped `stdin` at all reaching a debug hook wired there. Since a pending `AskUserQuestion`
is arguably the single most common "Claude needs you" moment in practice, `PreToolUse` scoped to
that one tool name fires the same alert right as the question is posed, before the tool blocks
waiting on a reply.

`petsend` = ~30-line Swift or Go binary: connect to socket, write one line, close, exit 0.
**Must always exit 0 and never block** — a hook that hangs hangs Claude Code. Add a 200ms
connect timeout and silently succeed if the pet isn't running.

**2. Cowork / Claude Desktop** — Cowork runs on Claude Code under the hood, so run
**Experiment 1** (below) before writing any code. If hooks don't fire, fall back to an
`FSEventStreamCreate` watcher on:
`~/Library/Application Support/Claude/local-agent-mode-sessions/` — a session dir writing
new bytes then going quiet for ~1.5s ≈ "response finished."

**3. claude.ai in the browser** — no hook exists. Chrome MV3 extension, content script on
`https://claude.ai/*`, `MutationObserver` on the message list; when the stop/send button
flips back to "send" state, the response is done → `fetch("http://127.0.0.1:8787/event")`.
Requires the pet to also listen on a loopback HTTP port. **Phase 3 — most fragile, ships last.**

---

## 3. Milestones

| # | Deliverable | Done when |
|---|---|---|
| 0 | Xcode project, LSUIElement, transparent floating panel with a red square | Square floats over all apps, drags smoothly, survives Space switches |
| 1 | Sprite loader + idle animation | Pet breathes at 12fps, crisp on Retina, <1% CPU |
| 2 | Socket server + `petsend` CLI | `petsend done test` makes it jump |
| 3 | Claude Code hooks wired | Real `claude` prompt → thinking → jump on completion |
| 4 | Sleep timer + wake, position persistence, menu bar settings | Sleeps after 5 min, wakes on event or click, remembers spot across restarts |
| 5 | Cowork emitter (hooks or FSEvents) | Cowork response → jump |
| 6 | Launch at login, signing, polish | Survives reboot |
| 7 | *(stretch)* Chrome extension | claude.ai response → jump |

Ship 0–4 first. That's the actual product; 5–7 are bonus surfaces.

---

## 4. Gotchas that will actually bite you

- **App Nap** suspends your timers when the app is backgrounded → pet freezes. Hold a
  `ProcessInfo.processInfo.beginActivity(options: .userInitiatedAllowingIdleSystemSleep, ...)`
  token, or drive frames off `CVDisplayLink`.
- **Multi-monitor coords.** macOS screen origin is bottom-left and differs from
  `NSEvent.mouseLocation` conventions. Persist position as *(screen UUID, fraction of frame)*,
  not raw points — otherwise the pet lands off-screen when you undock.
- **Hook latency.** Spawning a process per hook costs 5–20ms. Use a compiled binary, not a
  shell/Python script, or you'll feel it on `PostToolUse` (which fires constantly).
- **Stale socket file.** If the app crashes, `~/.claudepet/pet.sock` lingers and `bind()` fails
  with EADDRINUSE. Unlink before bind on startup.
- **Sandbox.** Enabling App Sandbox blocks the socket path and hook access. Don't sandbox —
  you're not shipping to the App Store. Do sign + hardened runtime so Gatekeeper is quiet.
- **`Stop` fires on subagent stops too** if you also wire `SubagentStop`. Pick one or the pet
  jumps constantly.

## 5. Security notes (relevant to your track)

- Socket dir `~/.claudepet/` → `chmod 700`, socket `0600`. Unix sockets honor filesystem perms;
  this keeps other local users out.
- If you add the HTTP listener for the browser extension, **bind `127.0.0.1` only, never
  `0.0.0.0`**, and require a shared secret header. An open localhost port is a real local-priv
  pivot and browser pages can hit it via CORS if you're sloppy.
- Treat inbound event JSON as untrusted: length-cap lines, whitelist the `event` enum, never
  interpolate `message` into anything executable.
- The Chrome extension: scope `host_permissions` to `https://claude.ai/*` exactly. A wildcard
  content script on `<all_urls>` is a keylogger waiting to happen.

---

## 6. Experiments to run before writing code (30 min total)

**Experiment 1 — does Cowork honor `~/.claude/settings.json` hooks?**
Add a `Stop` hook that runs `date >> /tmp/hooktest.log`. Send a message in Cowork and in
Claude Code CLI. Compare. This single test decides whether milestone 5 is 10 lines or 200.

**Experiment 2 — hook payload shape.**
Hooks receive JSON on stdin. Dump it: `cat > /tmp/hookpayload-$(date +%s).json`. Confirm
whether you get session ID, tool name, cwd — determines if you can do per-session pets later.

**Experiment 3 — transparent NSPanel over fullscreen apps.**
Ten-line Xcode project. Verify the panel actually floats over a fullscreen Terminal/browser
with the collection behavior above. If it doesn't, everything else is moot.
