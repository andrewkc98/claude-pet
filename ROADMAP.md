# Claude Pet — Post-v1 Roadmap

**Product thesis:** this is an *ambient status indicator* that happens to be cute. Cuteness
gets it onto the screen; information keeps it there. Prioritise accordingly.

**Success metric:** is it still running 30 days from now? Nothing else matters. Every item
below is ranked by its effect on that number.

---

## Tier 0 — Do before anything else (1 week, ~0 code)

### 0.1 Dogfood and take notes
Run it for a full working week. Keep a running list of every time it annoyed you, every time
it told you something useful, and every time you looked at it and it was wrong.

This is not filler. You currently have **zero** evidence about which of the items below
matters, and building on guesses is how side projects die with six features and no users.
Expect this week to reorder the entire list.

Specific things to note:
- Does the jump read as celebratory, or as a distraction that yanks your eye off the code?
- Is the 5-minute sleep timeout right? Too fast feels dead; too slow feels unresponsive.
- Do the thinking dots earn their place, or do you tune them out?
- How often is the state simply *wrong* (jumped when nothing finished, slept mid-task)?

### 0.2 Crash and restart hardening
Whatever you learn, the pet must survive: Mac sleep/wake, display disconnect, Claude Code
crashing mid-session, the pet itself being force-quit (stale socket), and a Space/fullscreen
switch. Any of these breaking silently means you stop trusting it, and once you stop trusting
it you close it.

---

## Tier 1 — High value, low effort (the real v1.1)

### 1.1 Blocked / needs-you state  ← **highest value item on this list**
The `Notification` hook fires when Claude Code is waiting on a permission prompt. Today that
means you tab back to a terminal that's been idle for four minutes doing nothing.

A distinct visual — cat sits up, ears forward, "!" emote, maybe a slow pulse — turns the pet
from decoration into something that saves you real time. This is the single upgrade most
likely to make the thing indispensable.

Effort: one emote + one state. Art: optional (reuse idle + "!" overlay).

### 1.2 Error / failure state
Distinguish "finished successfully" from "finished badly." Hook payloads carry enough to tell
when a tool call failed or a session ended abnormally. A flat-eared, tail-down pose reads
instantly and saves you reading scrollback to find out whether it worked.

### 1.3 Long-task awareness
If THINKING persists past ~2 minutes, change the presentation — curl up but stay awake, slow
the dots. Signals "still going, settle in" versus "just a sec." Cheap, and it fixes the
current failure mode where a 10-minute task and a 10-second task look identical.

### 1.4 Click interactions
Click to wake. Click to dismiss the "!" once acknowledged. Right-click for a context menu
(hide, settings, quit). Small, but it's the difference between a widget and an ornament.

---

## Tier 2 — The chat surface (Milestone 7 territory)

**Be honest about the cost/benefit here.** This is the most fragile component in the whole
project and the one most likely to break without warning.

### 2.1 If you use claude.ai in a browser
Chrome MV3 extension, content script on `claude.ai/*`, `MutationObserver` watching for the
stop-button → send-button flip that marks a completed response. Posts to a loopback HTTP
listener on the pet.

Risks, stated plainly:
- Claude.ai's DOM is not an API. A frontend deploy can break your selectors any day, with no
  warning and no changelog.
- You're adding an HTTP listener to an app that currently only speaks over a
  permission-protected Unix socket. Bind `127.0.0.1` only, require a shared-secret header,
  and scope `host_permissions` to `https://claude.ai/*` exactly.
- Expect to re-fix selectors every few months. Budget for maintenance, not just build.

### 2.2 If you use the Claude desktop app
The extension approach does not apply — it's a native app, not a browser tab. Options are
worse: Accessibility API observation, or watching its support directory for file activity the
way the Cowork fallback would have. Lower fidelity, more brittle.

**PM call:** do this only if you actually spend meaningful time in chat. If 90% of your Claude
use is Code and Cowork — which the hook work suggests — the honest answer is that this is a
lot of fragile surface area for a small slice of coverage. Revisit after the dogfood week
tells you where your time actually goes.

---

## Tier 3 — Depth (only after Tiers 0–1 prove out)

### 3.1 Reactive idle variety
Occasional groom, sit, lie-down, look-around — picked at random during long idles. Meaningfully
raises the ceiling on how long the pet stays charming. Pure art cost, no architecture.

### 3.2 Walking / repositioning
Cat wanders a short distance and settles. Big charm win, meaningful effort: walk cycle, path
logic, edge/multi-monitor handling. The single most "alive"-feeling upgrade available.

### 3.3 Session-aware behaviour
Different accent colour or accessory per project directory, or per source (Code vs Cowork vs
chat). Useful if you run several sessions at once; pointless if you don't.

### 3.4 Streak / activity memory
Pet is perkier on days you've been active. Fun, but be careful — anything that guilt-trips you
about not working is a feature you will grow to resent. Ship it only if it stays warm.

### 3.5 Sound
One soft chirp on completion, off by default. Low effort, and genuinely useful when the pet is
on a second monitor you aren't looking at. Must be trivially muteable.

---

## Explicitly NOT doing yet

- **Multiple pets / pet switching.** Complexity multiplier, no evidence of demand.
- **Feeding, stats, needs, Tamagotchi mechanics.** A pet that demands attention competes with
  your work. This one's job is to report on it.
- **Packaging for other people.** Requires Developer ID ($99/yr), notarization, an updater,
  settings migration, and support. Do it only if someone actually asks.
- **Rewriting the emote layer into a general plugin system.** Classic side-project death:
  building the framework before you have three things that need it.

---

## Suggested order

```
Week 1      Dogfood + notes (Tier 0)          ← do not skip
Week 2      1.1 blocked state, 1.4 clicks
Week 3      1.2 error state, 1.3 long-task
Week 4      Re-read your notes. Re-rank. THEN decide on Tier 2 vs Tier 3.
```

The Week 4 step is the actual PM discipline. The plan above is a hypothesis; your notes are
data. Anyone can write a backlog — the skill is throwing out the parts your own usage
disproved.
