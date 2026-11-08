# Assumptions

The brief says: *make assumptions instead of asking, note them and keep going.* These are the assumptions, grouped by topic. Each one says where it is enforced, so you can change it.

## Input

| # | Assumption | Why | Where to change |
|---|---|---|---|
| A1 | Timestamps are **per episode** (each episode starts near 00:00) and each episode is its own video file. If an episode's first timestamp is > 30 s, the times are treated as show-absolute and shifted to 0. The offset is recorded. | Editors cut each episode file separately, and EDL reels are per episode. | `parser.resolve_times` |
| A2 | The screenplay layout is **unknown in advance**, so the parser accepts six layouts and mixes of them: bracketed TC + `NAME:`, pipe/tab tables with ranges, classic NAME-on-its-own-line, labelled `ACTION:`/`SFX:` lines, SRT/VTT, CSV/JSON beats. | The input pack was not available while building. | `ingest/parser.py`, `extractors.py` |
| A3 | A timestamp is the **start** of the line or action. The end is the next line's start, unless a range (`00:12 - 00:15`) gives it. The last line of an episode is held for ≥ 2 s. | This is the most common convention in timed scripts. Microdramas hold the last frame. | `resolve_times` |
| A4 | Lines without a timestamp are either wrapped continuations (merged into the previous line) or new lines whose time is **interpolated by word count** (2.6 words/s). They are marked `timed=False` and promos built on them get an `interpolated_timing` flag. | Never drop content silently, never pretend a guessed time is exact. | `config/default.yaml → parser` |
| A5 | Episode numbers come from headers in the text (`EPISODE 12`, `Ep 12:`, `S01E12`) first, then from the file name, then file order. A file can hold several episodes. If a file has no headers but the clock resets, it is split there. | Real packs mix "one file per episode" with "one big PDF". | `parser.split_episodes`, `loader.episode_from_name` |
| A6 | Duplicate episodes (the same episode as .txt and .pdf) keep the copy with more lines and log a warning. | The safest choice when the same content arrives twice. | `parser.parse_docs` |
| A7 | PDFs have selectable text. Scanned PDFs get a clear error that suggests OCR (`ocrmypdf`). | OCR adds heavy dependencies for an unlikely case. | `extractors.extract_pdf` |
| A9 | **The real pack's block layout** (`**NAME (manner):**` / `Start: (mm:ss.ff) \| End: (mm:ss.ff)` / text) is the reference format, but the reader is not tied to it. Labels, timings and text may come in any order, on one line or several. Unknown layouts fall back to a structure-agnostic reader. | The layout of the next show is not guaranteed. | `ingest/parser.py`, `docs/robustness.md` |
| A10 | `CAMERA` blocks are kept as their own beat type. They count towards what's on screen and can carry the cliffhanger ("cut to black"), but their hook weight is 0.6× and intensity 0.7×: a shot description is evidence of a moment, not the moment. | 47% of the real pack's blocks are camera notes. Ignoring them loses visual information; trusting them fully lets "close-up on…" dominate. | `analysis/features.py` |
| A11 | Beats can **overlap** (a shot runs while a line is spoken). They are sorted by start, a clip ends at the latest end inside it, and a clip never ends while the next beat is already playing. | Editors can't cut in the middle of a line or a shot. | `models.Episode.span_end`, `generate/candidates.py` |
| A12 | `EPISODE LOGLINE`, `CONTINUITY NOTES` and similar header fields are metadata, not dialogue. The logline is shown to the LLM as context. "Picks up directly from…" lowers the stand-alone score of clips that open in an episode's first 12 s. | They are written for the production team, not spoken on screen. | `ingest/parser.py`, `analysis/standalone.py` |
| A13 | `LADY JULIANA` and `JULIANA` are the same character when both speak (honorifics are merged); `LORD ASHCROFT` stays as it is when no `ASHCROFT` speaks. | Character counts and "off-screen name" checks would otherwise double-count. | `analysis/characters.py` |
| A8 | The input pack is **confidential**: it is git-ignored, kept out of the Docker image and the Vercel bundle, and the UI reads it from the server only inside `INPUT_ROOT`. | The brief asks not to publish it. | `.gitignore`, `.vercelignore`, `.dockerignore`, `backend/app.py` |

## What a promo is

| # | Assumption | Why |
|---|---|---|
| P1 | Length is **20–60 s** of screen time, measured as the sum of its segments. Platform presets narrow this: TikTok 20–35, Reels 25–45, Shorts 30–60. | From the brief. The presets are a judgement call about where each platform performs. |
| P2 | Cuts happen **only on beat boundaries**, never mid-line. | Editors cut on lines. A mid-line cut is never what anyone wants. |
| P3 | **Hook** = the strongest hook cue among the beats that start in the first 3 s, decaying with delay. The tool trims dead air before the hook when that keeps the clip ≥ 20 s and scores higher. | From the brief ("something in the first 3 seconds"). |
| P4 | **Cliffhanger** = the cliff strength of the last beat (or the one before it if the last is a short reaction), minus resolution cues, **plus a "tease"** when the very next beat is a big reveal (cutting just before a payoff is the classic promo move), plus a bonus when the cut lands on the episode's own ending. | ReelShort/DramaBox promos usually cut one beat before the reveal. |
| P5 | **Stands alone** = starts with full context. It is penalised for opening on an unexplained pronoun or a reply, for references to earlier events, for answering a question asked off-clip, for off-screen names, for more than 4 speakers and for more than 2 scene changes. | A new viewer has none of the show's history. |
| P6 | Multi-segment promos are allowed but conservative: at most 3 per list, a 0.9× score penalty, a stand-alone penalty per jump, and segments must share a main character. | The brief allows them. Bad stitches confuse more than they hook. |
| P7 | The brief asks for **moments, not edits**: no music, captions or overlays. The ffmpeg script only cuts raw ranges for preview. | From the brief. |

## Ranking and posting

| # | Assumption | Why |
|---|---|---|
| R1 | The default weights are hook 0.30, cliffhanger 0.25, stand-alone 0.15, intensity 0.12, pace / length / trope 0.05 each, episode end 0.03, spoiler −0.08. | Hook and cliffhanger are the brief's two named criteria. Stand-alone is the third. `promo-finder learn` re-fits these to your picks. |
| R2 | At most 3 promos per episode, overlap IoU ≤ 0.35, and MMR for variety, so a week of posts tests different angles. | Ten cuts of the same slap is not a list. |
| R3 | The posting order leads with spoiler-safe episodes (first 40% of the show) and the strongest hooks, alternates tropes, and holds late-season reveals for later waves. | Viewers who tap through should land near the start of the story. A/B-ing angles shows what converts. |
| R4 | Promos scoring below 45 are not returned (default: up to 30 per show). | Editors should review strong candidates, not filler. Adjustable in the UI. |
| R5 | The **trope value** ranking (slap/humiliation > hidden identity > pregnancy ≈ betrayal > revenge…) reflects what ReelShort/DramaBox ads lead with. It is a judgement, not data. | Tunable in `lexicons.yaml → trope_value`. |

## AI / LLM

| # | Assumption | Why |
|---|---|---|
| L1 | The tool must work with **no key** (free, offline, deterministic), and an LLM is an optional precision layer. | Free tiers rate-limit, interview environments vary, and rules are auditable. |
| L2 | **One key selects the provider**: the key prefix picks it and the model is discovered from `/models`. Override env vars exist for unusual setups. | You asked for it, and the brief says "a solution where the model is easy to swap will shine". |
| L3 | Only the top 30 candidates go to the LLM, 5 per call, as numbered lines. The LLM may tighten cut points only to real lines inside the clip and within length limits. Final = ½ rules + ½ LLM. | Cost scales with N, not with show length. Numbered lines stop invented timestamps. The 50/50 blend stops either side from dominating. |
| L4 | When the LLM fails, the run continues on rules and the failure is logged in the report. | A promo tool should never block an editor. |
| L5 | Keys pasted in the UI are used for one request and never stored or logged. Keys are masked in every response. | Basic hygiene. |

## Evaluation

| # | Assumption | Why |
|---|---|---|
| E1 | A tool promo **matches** a manual promo when temporal IoU ≥ 0.30 **or** it covers ≥ 50% of the manual promo. Matching is one-to-one (greedy by IoU). Any overlap below that counts as "partial". | Editors' and the tool's boundaries differ by seconds. The moment is what matters. Coverage catches tool clips that contain the editor's tighter cut. |
| E2 | Recall against the editor is the headline metric. Precision against the editor is reported but expected to be low (the tool returns more promos than an editor lists). | A missed great moment costs more than an extra candidate to skip. |
| E3 | The **sample show** (8 episodes) is original synthetic content written for this repo. Its manual promos were picked by the same author before running the tool, so its agreement numbers are a smoke test, not a benchmark. | Honesty: the real benchmark needs the real pack and an independent editor's picks. |
| E4 | Editor keep/reject clicks are training data, not ground truth. The learner blends learned weights 50/50 with the hand-set ones. | A few dozen labels should not erase sensible priors. |

## Deployment

| # | Assumption | Why |
|---|---|---|
| D1 | On Vercel free: 4 MB uploads (zip the pack), a 60 s function limit, and no persistent disk (runs and feedback in `/tmp`, exports are stateless). For the full pack with an LLM, use Docker or the CLI. | Vercel Hobby limits. |
| D2 | Timecodes in the EDL and cut sheet are 30 fps non-drop. | Common for vertical social video. Change `FPS` in `export/editor_formats.py`. |
