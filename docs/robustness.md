# Robustness: input-structure proofing, failure points and fallbacks

The tool has to run on a show nobody has seen before, in a layout nobody has seen before, during an interview. Every stage that could stop a run has a fallback, and every fallback says what it did in the run's warnings (`promos.json → warnings`, the Quality tab, `metrics.degraded_stages`).

## 1. Input structure: how layouts are handled

| Layer | What it does | Fallback when it fails |
|---|---|---|
| **File type** | Extension → reader (txt, md, fountain, rtf, pdf, docx, odt, html, srt, vtt, csv, tsv, xlsx, json, zip). | Wrong or missing extension → **content sniffing** (PDF/ZIP/DOCX/ODT/XLSX magic bytes, HTML, JSON, printable text). A reader that errors → the sniffed type → plain text. Images, video and old binary Office files are skipped with a hint ("save as .docx"). |
| **Containers** | Folders (recursive), zips in memory, zip-in-zip up to 3 levels, 300 MB budget. | `__MACOSX`, `.DS_Store`, `~$` temp files, README/LICENSE and manual-promo files are never read as episodes. A corrupt zip is skipped with a warning. |
| **Encoding** | UTF-8 (with/without BOM), UTF-16, cp1252, latin-1. | Last resort: UTF-8 with replacement characters. |
| **Episode boundaries** | `EPISODE 4`, `Ep 4:`, `S01E04`, `EPISODE NUMBER: Episode 4` headers; several episodes per file. | Clock resets to 0:00 → split. File name (`episode-004-…`, `Ep_04`, `S01E04`, `04.txt`) → order of files. Header and file name disagree → header wins, warning. Duplicates → keep the fuller copy, warning. |
| **Metadata** | `EPISODE LOGLINE`, `CONTINUITY NOTES`, `TITLE`, `SYNOPSIS`, … are stored on the episode, never parsed as dialogue. | The logline goes to the LLM as context; continuity notes ("picks up directly from…") lower the stand-alone score of clips that open on the carried-over cliffhanger. |
| **Line grammar** | One state machine reads labels, timings and text **in any order and on the same or separate lines**: `[00:07] AVA: line`, `00:03 - 00:06 \| AVA \| line`, `**AVA (Cold):** / Start: (00:13.50) \| End: (00:14.30) / "line"`, classic `00:07 / AVA / (whispers) / line`, `Scene heading:` / `Scene start:` fields, transitions. | Markdown bold, bullets, NBSP, tabs, CRLF, ALL-CAPS or Title-case labels, 1–3 parentheticals (`(O.S.) (Firm)`), names starting with "THE". |
| **Structure-agnostic reader** | If the main reader's output looks broken (timecodes leaking into text, "START" as a speaker, < 30% timed), every line holding a timecode is re-read as a beat. | Picked only when it scores clearly better; the choice is logged. |
| **Timing** | Ranges, start-only, `mm:ss.ff`, `hh:mm:ss,ms`, SMPTE frames, `1m23s`. | Missing times interpolated by word count and flagged. Show-absolute times shifted to 0. Backwards jumps clamped (start-only formats) or sorted (overlapping ranges). A beat longer than 45 s (typo) is re-estimated. |
| **Overlapping beats** | Camera shots overlap dialogue in the real pack. Beats are sorted by start, clips end at the latest end inside the window, and a clip never ends while the next beat is already playing. | — |
| **Stray documents** | A file with no timestamps among timed episodes (notes, synopsis) is ignored with a warning. | If *nothing* is timed, everything is interpolated and every promo is flagged `interpolated_timing`. |

Verified by `tests/test_robustness.py` (12 mutations of the same episode: CRLF, no markdown, lower-case labels, extra/no blank lines, bullets, inline timing, `Start … End` without a pipe, `hh:mm:ss`, NBSP + tabs, UTF-16; wrong/missing extensions; zip without `.zip`; HTML; ODT; no timestamps; garbage) and `tests/test_block_format.py`. On the real pack: **50/50 episodes, 3,727/3,727 blocks, 100% timed, 0 warnings.**

## 2. Single points of failure and their fallbacks

| # | Failure point | Fallback / guardrail | Test |
|---|---|---|---|
| 1 | `config/default.yaml` missing, corrupt or partial | Built-in copy (`promo_engine/defaults.py`) underneath, YAML merged on top, so required keys can never disappear | `test_corrupt_config_falls_back_to_builtin` |
| 2 | `config/lexicons.yaml` missing or incomplete | Built-in lexicon | same |
| 3 | A typo'd regex in the lexicon | That one pattern is skipped and reported; the others work | `test_bad_regex_in_lexicon_is_skipped` |
| 4 | `learned_weights.yaml` with garbage values | Only known keys within 0–5 are applied | — |
| 5 | Built-in copy drifts from the YAML | A test fails until `python scripts/sync_defaults.py` is run | `test_builtin_defaults_match_yaml` |
| 6 | A file cannot be read | Skipped with a warning; the other files continue | `test_wrong_and_missing_extensions` |
| 7 | The parser throws on one episode | Fallback reader for that episode, or skip it with a warning | — |
| 8 | Candidate generation throws on one episode | That episode is skipped; the others still produce promos | — |
| 9 | Refinement, montages, characters, signals, schedule, quality, metrics or heatmap throw | The stage is skipped with a safe default; `metrics.degraded_stages` lists it | `test_failing_stage_degrades_not_dies` |
| 10 | Nothing reaches `min_score` | The best available candidates are still returned, flagged `below_min_score`, with a warning | `test_min_score_relaxation_flags_instead_of_returning_nothing` |
| 11 | One promo cannot be described | That promo is dropped; the others are kept | — |
| 12 | **LLM key invalid / quota / outage** | **Fallback chain**: `LLM_API_KEY=key1,key2` or `LLM_FALLBACK_API_KEYS`; the next provider takes over automatically | `test_llm_fallback_chain_switches_provider` |
| 13 | LLM keeps failing | **Circuit breaker** after 2 consecutive failures: no more calls, rules ranking kept | `test_circuit_breaker_and_budget` |
| 14 | LLM too slow (Vercel's 60 s limit) | **Time budget** (`llm.max_total_seconds`, 45 s on Vercel); remaining batches stay rules-ranked | same |
| 15 | LLM returns junk JSON or invented timestamps | Loose JSON repair; line-number answers validated against real beats; invalid edits rejected and counted | `test_llm_boundary_edits_are_guarded` |
| 16 | LLM step crashes halfway | All candidates are rolled back to their pre-LLM state | `test_failing_llm_falls_back_to_rules` |
| 17 | Model name retired | Model discovered from the provider's `/models`; default as last resort | — |
| 18 | Manual promos file malformed | Bad rows skipped with warnings; the run continues without a comparison if nothing is readable | `test_load_manual_*` |
| 19 | One export fails | The others are still written; `EXPORT_ERRORS.txt` explains | `test_export_failure_is_isolated` |
| 20 | Network blip while the browser polls a job | Up to 6 retries with back-off, 15-minute ceiling, clear message | — |
| 21 | Upload too large / zip bomb / path traversal | 413 with advice; 300 MB uncompressed budget; server folders limited to `INPUT_ROOT` | `test_server_path_is_sandboxed` |
| 22 | Serverless instance forgets a run | Exports are stateless (the browser posts the run back) | `test_sample_and_stateless_exports` |
| 23 | Browser storage blocked | Every read/write is wrapped; the app works without it | — |

## 3. What still needs a human

- **Taste**: the rules read words, not pictures. Hooks that live in a look or a camera move are under-scored. Promos whose hook is an action line are flagged `visual_hook`.
- **Keyword-level hooks**: a line like `"Poison?"` counts as a physical shock and a mention of a "sword" counts as action. The LLM judge (any key) re-scores the shortlist and catches most of these.
- **Unknown vocabulary**: a new genre (sci-fi, sports) may need a few words added to `config/lexicons.yaml`. Then run `python scripts/sync_defaults.py`.
