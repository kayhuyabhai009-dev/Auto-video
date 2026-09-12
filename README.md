# Auto Video Producer — HUMAN SYSTEMS NOIR

An **advanced automatic video producer** for the channel style
**HUMAN SYSTEMS NOIR — evidence-led psychological documentary**.

This is not a manual editor. The primary workflow is:

```
LOAD SCRIPT → GENERATE TTS → ANALYZE AUDIO → SEGMENT SCRIPT →
SELECT EXISTING ASSETS → BUILD TIMELINE → ADD SUBTITLES →
ADD MOTION GRAPHICS → ADD TRANSITIONS → ADD GLOBAL EFFECTS →
ADD MUSIC → RENDER → EXPORT MP4
```

Configure the visual system once (preset + settings), then produce future
videos by **selecting a script and pressing GENERATE VIDEO**.

---

## Quick start

```bash
./setup.sh     # install python deps + verify ffmpeg (PyPI; imageio-ffmpeg fallback)
./run.sh       # start the studio on http://0.0.0.0:7860
```

Then open the studio UI:

1. **Produce** tab → load a script (paste, upload, or pick from `scripts/`)
2. Choose the narration source:
   - **Generate using TTS API**
   - **Use uploaded / pre-generated narration** (`.txt` package and/or `.wav .mp3 .m4a .flac`)
   - **Use existing project narration**
3. Pick a preset (default: *Human Systems Noir*)
4. Press **GENERATE VIDEO** and watch the pipeline monitor.

A demo script is included: `scripts/the_goalposts_never_stop_moving.txt`
(uses chapter markers and a `[[SOURCE: …]]` evidence tag).

## Requirements

- Python 3.11+, pip
- FFmpeg with libx264, libass, drawtext, zoompan (auto-resolved via
  `AVP_FFMPEG` env → system `ffmpeg` → `imageio-ffmpeg` wheel)
- No API keys required to run: the default TTS provider is the **fully
  offline espeak-ng engine** (bundled via `espeakng-loader`). Cloud TTS
  (OpenAI / ElevenLabs / custom HTTP) is configurable, and keys are read
  **only from environment variables** (never stored):
  `export TTS_API_KEY=…`

---

## What the system does (and deliberately does not do)

### Asset-only principle
The producer works **from your local Asset Library only**
(`assets/stock_images`, `assets/stock_videos`, …). It never generates
replacement images, never downloads random internet images, and never
silently introduces AI visuals. If nothing matches, it degrades through a
documented fallback chain — other suitable asset → symbolic texture →
designed typography card → hold the current visual — and **flags the scene
for human review** instead of pretending a missing asset was found.

*(The starter images in `assets/stock_images/` were generated locally at
setup, are tagged `source=generated_starter / license=owned`, and exist so
the demo pipeline works out of the box — delete or replace them freely.)*

### Semantics, not random images
Every segment is classified into a **script role** (HOOK_SIGNAL, PROBLEM,
PROMISE, DEFINITION, SOURCE, EXAMPLE, MECHANISM, COUNTEREXAMPLE,
EMOTIONAL_RECOGNITION, PRACTICAL_MOVE, LIMITATION, RECAP, NEXT_WATCH) and
tagged with **concepts** from a noir lexicon (~70 concepts tuned to
observable objects/actions: phone, document, door, hands, clock, ledger —
never "an angry face as proof of manipulation"). Asset selection scores
candidates with configurable weights:

```
semantic_match·0.45 + scene_match·0.20 + format_match·0.10
+ duration_match·0.10 + diversity·0.10 + quality·0.05
− recent-use penalty − reuse penalty
```

### No-cut intelligence
The engine explicitly decides **not** to cut when meaning hasn't changed:
hold-chains collapse into a single continuous clip at render time.

### Editing rhythm
No fixed cut interval. Per-role second-ranges (configurable in Settings),
tighter beats in the first 30 seconds, slower for counterexamples, emotional
recognition and endings.

### Transitions
Weighted pool (hard_cut 50, fade 20, zoom 10, slide 10, blur 5, …) but the
pool is gated by **narrative state change** — complex transitions only when
the semantic state actually changes. Evidence pivots (amber dip) are
boosted when the narration cites a source.

### Subtitle engine
ASS/libass-based. Cinematic **selective** mode by default; **FULL CAPTION**
mode for accessibility. Semantic word coloring (bone normal; oxide red
pressure; signal blue agency; amber sources; gray uncertainty), per-word
typewriter timing, fade/pop/slide/word-highlight animations, max chars /
max lines / position / full style control.

### Motion graphics (NOT subtitles)
23 designed information-card templates (fact, number, list intro, evidence
CLAIM/SOURCE/DATE/LIMIT, mechanism map, timeline, playbook rail
NOTICE→REGULATE→VERIFY→BOUNDARY→BUILD, counterexample OBSERVED vs
INTERPRETED vs ALTERNATIVE, warning, statistic, quote, decision tree, plus
motif cards: red thread, boundary line, ledger, door, clock, document,
waveform). Phrase triggers ("three facts", "step one", "warning",
"according to a 20xx study"…) and role-driven chances place them; they
render as transparent PNGs with entrance/exit animation on layer 4.
Add your own as JSON in `assets/motion_graphics/templates/`.

### Global effects layer
Film grain, vignette, dust (screen-blend), letterbox, scanlines — applied
over the whole video, opacity/blend/enable configurable.

### Music & SFX
Six procedural noir beds ship in `assets/background_music/` (hook pulse,
documentary bed, open tape, sparse tension, near-silence, resolve warm).
Music **evolves with the structure** (dark pulse → sparse bed → open sound
→ near silence at caveats → resolved ending), is sidechain-ducked under
narration, and loudness-normalized. SFX (paper, click, door, riser,
impact) fire only when semantically justified with a minimum gap.

### TTS-first, narration is master
Whatever narration you supply or generate **is** the master timeline —
visuals, subtitles, music and effects all adapt to its exact duration.
Word timestamps are used when the provider supplies them (ElevenLabs
character alignments, custom JSON), otherwise timings are distributed
estimates **clearly flagged** (`timing_mode: estimated` + review flag).

### Pre-generated TTS support
- `# PRE-GENERATED TTS` `.txt` package with `audio: file.wav` reference
- JSON package `{"text": …, "audio": …, "word_timestamps": […]}`
- plain audio upload (`.wav .mp3 .m4a .flac`)

If a valid narration source exists it is **never** re-synthesized unless
you explicitly choose to regenerate. A text-only package's text is adopted
as the **authoritative script** (never rewritten or paraphrased).

### Projects
`projects/<id>/` stores script, narration source + file, audio duration,
segmentation, timeline, subtitles, motion graphics, render settings and the
MP4. Reopening reuses stored narration. The **Timeline** tab lets you
inspect every segment, swap assets, change motion/transition, lock scenes,
and **Regenerate scene** or re-render without re-running TTS or planning.

---

## Layout

```
app/               engine (FastAPI server + pipeline modules)
  lexicon.py         concept/role/evidence/accent knowledge base
  segmentation.py    semantic segmentation + timing alignment
  decision_engine.py asset scoring, cut/hold, transitions, review flags
  tts.py             provider matrix (offline + cloud) + package parser
  subtitles.py       ASS generation with semantic color logic
  motion_graphics.py 23 Pillow-rendered card templates
  renderer.py        FFmpeg pipeline (units → assembly → final pass)
  effects.py         procedural music/SFX/texture seeds + global FX
  asset_library.py   scan, metadata, tagging, scoring
  projects.py        persistence
  pipeline.py        orchestrator
  settings.py        persisted settings (secrets only via env)
assets/            YOUR library (10 categories, auto-scanned)
presets/           Human Systems Noir + 4 genre variants (editable JSON)
scripts/           script library
static/            studio UI (single-page, noir styled)
projects/          one folder per project (script→mp4)
```

## API (selected)

```
POST /api/projects                         create project
POST /api/projects/{id}/generate           full pipeline (the big button)
POST /api/projects/{id}/narration_upload   pre-generated TTS (.txt) or audio
POST /api/projects/{id}/render             re-render from timeline (no TTS)
POST /api/projects/{id}/rebuild_timeline   re-plan (no TTS)
POST /api/projects/{id}/regenerate_scene/{sid}
PATCH /api/projects/{id}/segments/{sid}    advanced edits
POST /api/library/scan · GET/POST /api/assets[/{id}]
GET/POST /api/settings · POST /api/tts/test
GET  /api/presets · POST /api/presets/{name}/apply · POST /api/presets
POST /api/segmentation/preview             dry-run roles/concepts on text
```

## Design notes

- Palette is exactly: obsidian `#111315`, charcoal `#20252A`, bone
  `#E8E2D6`, oxide red `#C94A3D`, signal blue `#5E8EA5`, muted amber
  `#D0A457`, uncertainty gray `#9BA3A8`.
- Darkness creates focus, not fear: no skulls, no permanent glitch, no
  permanent red tint, no random scary faces.
- Counterexample discipline: OBSERVED is visually separated from
  INTERPRETED; alternative explanations get gray; practical responses get
  blue. Evidence cards always expose what a claim does **not** prove.
- Review flags never lie: typography fallbacks, weak matches, estimated
  timing and placeholder narration are all surfaced to the human.
