# Pet Art Spec — Coral Cat

Companion to PET_PLAN.md. Lock this before writing the sprite loader (Milestone 1).

---

## 1. Hard technical constraints

| Property | Value | Why |
|---|---|---|
| Frame size | **64 × 64 px** | A cat needs ears, legs, and a tail to read. 32px loses them. |
| Sheet layout | One PNG per animation, frames in a **single horizontal row** | Loader math is `x = frameIndex * 64`. Trivial and hard to get wrong. |
| Transparency | True alpha, no matte | Any off-white halo will show against a dark wallpaper. |
| Palette | Exactly **7 colors** (below) + full transparent | Forces consistency; makes hand-editing frames fast. |
| Anti-aliasing | **None.** Hard pixel edges only | AA at 64px turns to mush when scaled on Retina. |
| Scaling in app | Integer only (2× → 128pt), `interpolation = .none` | Non-integer scaling destroys pixel art. |
| Orientation | **Side profile, facing right** | Jump and stretch are only legible from the side. Flip horizontally for facing-left later — free second direction. |

## 2. Palette (lock these exact hexes)

```
#2A1A16  outline / pupils      (warm near-black)
#8C4230  deep shadow
#A34F38  shadow
#D97757  base coat             ← Claude coral, the dominant color
#E89B7C  highlight
#F4D3C4  belly / muzzle / paws
#F7F3EE  eye whites, Zzz text
```

Use the outline color on the full silhouette edge. A dark outline is what keeps the pet
readable over *any* wallpaper — this is the single highest-value decision in the spec.

## 3. Base poses — you only draw THREE

Everything else is derived by editing these.

| Base | Description | Derives |
|---|---|---|
| **A. Standing side profile** | All four legs down, tail up and curved, ears alert, eyes open | idle, thinking, jump |
| **B. Curled ball** | Nose-to-tail circle, eyes closed as simple curved lines | sleep |
| **C. Arched stretch** | Classic cat stretch, front legs extended, back arched, rear up | wake |

## 4. Animation breakdown

Target **10 fps**. Frame counts assume you edit only the parts listed — the body stays put.

### idle — 6 frames, loops (from Base A)
Only the **tail and eyes** move. Body is pixel-identical across all 6.
- f1–2: tail curve right, eyes open
- f3: tail center
- f4: tail curve left, **eyes closed** (1-frame blink — 1 frame is enough at 10fps)
- f5: tail center, eyes open
- f6: tail right
Add a 1px vertical body bob on f3/f6 only if it still reads as breathing, not twitching.

### thinking — 4 frames, loops (from Base A)
Ears twitch + head tilts 1px. Signals "Claude is working" without being distracting.
Keep it subtle — this plays for minutes at a time and a busy loop gets annoying fast.

### jump — 8 frames, plays once (from Base A) ← **your money animation**
This is the one users actually watch. Spend your time here.
1. **Anticipation** — squash down, body 4px shorter/2px wider, legs compressed
2. **Launch** — stretch tall, body 4px taller/2px narrower, legs extended, ~6px off ground
3. **Rise** — ~14px off ground, legs tucked, tail streaming down
4. **Apex** — ~18px off ground, body neutral, ears up, tail loose (hold 2 frames' worth of feel)
5. **Descend** — ~12px off ground, legs reaching down
6. **Land squash** — ground level, maximum squash (6px shorter/3px wider)
7. **Recover** — slight overshoot, 1px taller than neutral
8. **Neutral** — identical to idle f1, so the transition back is seamless

Squash-and-stretch is what makes this feel alive rather than like a sprite being translated
upward. Do not skip frames 1, 6, and 7 — the anticipation and the landing are what sell it.

### sleep — 4 frames, loops (from Base B)
Curled ball, body nearly static. A "z" drifts up-right and fades over the 4 frames, with a
second "z" offset by 2 frames so it's a continuous stream rather than a pulse.
Optional: 1px body rise/fall for breathing.

### wake — 5 frames, plays once (B → C → A)
Curled ball → uncurl → full arched stretch (hold) → relax → neutral standing (= idle f1).
Ends exactly on idle f1 so the handoff is invisible.

---

## 5. Generation → cleanup pipeline

**Step 1 — generate Base A only.** Prompt an image model with:

> Pixel art sprite of a cat, side profile facing right, standing on all four legs, tail
> curved upward, ears alert, eyes open. Flat coral orange fur (#D97757) with cream belly
> and paws, dark warm outline. Limited palette, no gradients, no anti-aliasing, no shading
> detail. Plain solid background. Simple readable silhouette. 16-bit game sprite style,
> full body, centered.

Generate 10+ variants. Pick on **silhouette** — squint at it; if you can't tell it's a cat
from the black shape alone, reject it regardless of how cute the details are.

**Step 2 — normalize.** The output will be high-res with hundreds of colors and soft edges.

```bash
# downscale to the pixel grid, crush the palette, kill AA
magick input.png -resize 64x64 -dither None -posterize 4 -filter point output.png
```

Expect this to look rough. It's a starting point, not a finished frame.

**Step 3 — hand-clean in a pixel editor.** Non-negotiable step. Remap every pixel to the
7-color palette, redraw the outline by hand at 1px, fix the silhouette. Budget 1–2 hours.
This is where the sprite actually becomes good.

- **Aseprite** ($20) — the standard. Onion skinning and sheet export make animation sane.
- **LibreSprite** (free) — open-source fork, ~95% as good.
- **Piskel** (free, browser) — fine for this scale, weakest export options.

**Step 4 — draw Bases B and C** by editing A. Easier than it sounds: you already have the
palette, the proportions, and the outline style.

**Step 5 — animate.** Duplicate the base frame, edit only what moves, use onion skinning to
check alignment. Export each animation as a horizontal strip PNG.

## 6. Deliverables for Milestone 1

```
Assets/
  cat_idle.png      384 × 64   (6 frames)
  cat_thinking.png  256 × 64   (4 frames)
  cat_jump.png      512 × 64   (8 frames)
  cat_sleep.png     256 × 64   (4 frames)
  cat_wake.png      320 × 64   (5 frames)
```

## 7. Mistakes to avoid

- **Generating each frame with the model.** The cat will not be the same cat. Derive frames
  by editing; never re-generate.
- **Inconsistent baseline.** Every frame must have the paws at the same y-coordinate (except
  during `jump`), or the pet vibrates against the ground. Draw a guide layer and keep it.
- **Character not centered in the 64px box.** Center it once in Base A; all derived frames
  inherit it. Fixing this later means re-exporting everything.
- **Too much idle motion.** This thing sits on your screen for hours. Under-animate idle —
  you can always add motion, but a fidgety pet gets closed.
- **Skipping the outline.** Untested against a dark wallpaper, a soft-edged sprite vanishes.
- **Building the loader before the sheet layout is final.** Lock section 6, then write code.
