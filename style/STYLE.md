# AI-vs house style

The look of *AI vs obs-studio bugs* (commit a6962c7), written down so the next
video can reuse it. Exact numbers live in [`style.json`](style.json); the code
that applies them is in `tools/`.

## The idea
Enemy-of-the-week footage, with each enemy wearing the name of a real C/C++ bug.
The labels should look like part of the scene, not like stickers: the text is
warm and lit by the fog, the shadows are soft, and the motion is calm.

## Type
- **Antonio SemiBold (600)** for everything: labels, titles and the end card.
- **Text colour `#F2EAD5`**, a warm off-white keyed to the fog. Never pure white, never coloured.
- **Shadows** are a five-layer grayscale stack, the same as this CSS:
  `0 0 2px #000f2, 2px 2px 0 #000d9, 3px 4px 8px #000bf, 0 0 18px #0009, 0 0 36px #0004`
  (that's 0.95, 0.85, 0.75, 0.6 and 0.3 alpha).
- **`LABEL_SCALE` 2.0** keeps labels legible on a phone. Titles scale with it too.

## Labels
- **Heroes are never labelled.**
- **One baddie, one bug, locked forever.** IDs are `shot/slug` in `data/label_lock.json`.
- **Rank by menace:** violence² × screen time picks the worst bugs (use-after-free,
  data race, …). Minor bugs go to the fodder.
- **Anchor to a feature** (head, neck, muzzle, headlights) plus an offset. Long
  objects get a two-point axis, and the label rotates with it.
- **Smooth the motion:** smoothing spline (λ 40), then a zero-lag EMA (τ 3–4 frames).
  Static props get a fixed position.
- **Occlusion:** when a hero covers 30 % of a label, the whole label fades. Letters are never clipped.
- **Labels under 0.5 s are dropped.**

## Structure
1. **Cold open:** "AI" at 0:00, then "AI vs" at 0:00.75. Hold to the first cut, with a 6-frame fade-out.
2. **Reveal:** "obs-studio bugs" on the first horde shot.
3. **Battle:** labels only. One mid-film beat carries the URL in small type.
4. **Ending:** cut on the biggest action beat, then a **hard cut to black**. Hold
   1.2 s, then a true-black card: **BUGS REMAINING: N** and **github.com/obs-rust**
   in tracked caps. No vignette, grain or shadow.
5. **Audio:** splice the calm post-battle score under the cut (qsin crossfade 0.5 s,
   low-pass the outgoing battle, loudness-matched with ebur128). Fade it out over 2.4 s.

## Workflow rules
- Never modify the source footage.
- 720p previews only, until the 4K render is approved.
- Write outputs to `data/keyframes.assigned.json`. Never overwrite hand keyframes.

## Pipeline
```
tools/cuts.py            shot boundaries
tools/detect_owl.py      enemy detection (OWLv2)    tools/segment.py  hero masks (SAM2)
tools/restore_keyframes.py  hand keyframes, titles, anchors (source of truth)
tools/build_labels.py    ranked bug list
tools/assign_labels.py   merge + lock labels
tools/keys_to_tracks.py  keyframes → smoothed tracks
tools/render.py          RGBA overlay (PREVIEW_ONLY=1 for 720p)
tools/audio_splice.py    ending score splice plan
tools/end_card.py        composite + end card (--4k for the master)
```
