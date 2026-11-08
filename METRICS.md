# METRICS — test results and the numbers that matter

_Generated 2026-11-07 21:15 by `python scripts/generate_metrics.py`. Re-run it after adding the real input pack and your manual promos: `python scripts/generate_metrics.py --input data/input --manual data/manual_promos/my_manual_promos.csv`._

> **Honesty note.** The section *Real input pack* below is a run on Kuku's show. Brief-compliance numbers there measure the tool against its own thresholds (hook cue ≥ 0.4 in the first 3 s, cliffhanger ≥ 0.5, no context flags), so they show the picks are well-formed, not that they are the best promos. Agreement numbers (recall, cut-point error) are only meaningful against an editor's independent picks: the sample show's manual promos were picked by the same person who wrote the rules, so treat them as a smoke test. Re-run with `--manual` and your own picks for the real benchmark.

## Real input pack

- 50 episodes, 3727 lines/actions, 100% timestamped, runtime 3.7s, LLM: none (0 calls, 0 tokens).
- Brief compliance: length 100% · hook ≤3s 100% · strong cliffhanger 100% · stand-alone 100% · all three 100%.
- Output: 30 promos from 865 candidates, median 34.9 s; 10 episodes and 4 tropes in the top 10; 37% carry a warning flag; degraded stages: none.

| Rank | Post | Cut | Len | Hook | Cliffhanger | Score | Flags |
|---:|---:|---|---:|---|---|---:|---|
| 1 | 1 | Ep 15 00:47.4–01:26.0 | 39s | Physical shock: (The Thug with Cap violently shoves Juliana back with both hands; she  | Writer-marked cliffhanger | 90 | visual_hook |
| 2 | 3 | Ep 16 00:59.0–01:23.2 | 24s | Physical shock: (Alexander flexes his bleeding hand, showing no sign of pain.) | Writer-marked cliffhanger | 86 | visual_hook |
| 3 | 10 | Ep 23 01:22.0–02:11.5 | 50s | Physical shock: PRUDENCE (Muffled, Horrified): "Poison?" | Writer-marked cliffhanger | 85 | — |
| 4 | 8 | Ep 21 01:19.8–01:54.0 | 34s | Physical shock: PRUDENCE (Grateful, Choked with Emotion): "You saved him. The grand do | Writer-marked cliffhanger | 85 | — |
| 5 | 5 | Ep 11 01:07.5–01:52.8 | 45s | Shocking line: GERALD (Cruel, Condescending): "Stand aside. Look at this place. A per | Writer-marked cliffhanger | 83 | — |
| 6 | 2 | Ep 3 01:00.5–01:28.1 | 28s | Physical shock: (The guards forcefully grab Juliana by both shoulders and drag her bac | Reveal about to land | 83 | visual_hook |
| 7 | 13 | Ep 28 01:07.2–01:33.8 | 27s | Physical shock: BLOND NOBLEMAN (Commanding, Resolute): "Take her away before she poiso | Line cut off mid-sentence | 83 | — |
| 8 | 15 | Ep 29 01:24.0–01:49.0 | 25s | Physical shock: (The guards shove Juliana violently into the cell; she falls hard onto | Line cut off mid-sentence | 82 | visual_hook |
| 9 | 22 | Ep 41 00:58.0–01:36.1 | 38s | Physical shock: JULIANA (Defiant, Unbowed): "You needed an entire chapel to feel power | Writer-marked cliffhanger | 82 | spoiler_risk |
| 10 | 17 | Ep 30 01:05.3–01:44.4 | 39s | Reveal: ELDER NOBLEMAN (Pragmatic, Scheming): "A maid with herbs in her posses | Line cut off mid-sentence | 81 | — |

_No manual promos supplied yet: add them with `--manual` to get recall, cut-point error and the side-by-side table._

## 1. Test suite

**126 tests, 0 failures, 0 errors, 0 skipped — ✅ all passing** (9.8 s).

| Test file | What it covers | Passed | Failed |
|---|---|---:|---:|
| `test_analysis.py` | Hook / cliffhanger / resolution cues, false-positive guards, tropes, stand-alone penalties, characters | 6 | 0 |
| `test_api.py` | Health, sample run, all 9 exports, upload job flow, bad input errors, path sandbox, key masking, feedback | 7 | 0 |
| `test_block_format.py` | Kuku's block layout: every block timed, camera/action/SFX kinds, double parentheticals, metadata ≠ dialogue, overlaps, header-vs-filename numbering, alias merge | 8 | 0 |
| `test_compare.py` | IoU maths, one-to-one matching, miss diagnosis, manual CSV / JSON / free-text loading, sample recall | 6 | 0 |
| `test_e2e.py` | CLI run / parse / learn exactly as a user runs them | 3 | 0 |
| `test_exports.py` | CSV rows, cut sheet handles/order, valid CMX3600 EDL, ffmpeg script, HTML/MD reports, full output folder | 5 | 0 |
| `test_ingest.py` | Folders, nested zips, junk files, episode numbering, 6 screenplay layouts, interpolation, PDF furniture | 12 | 0 |
| `test_llm.py` | Key → provider detection (15 cases), env overrides, JSON repair, cache, mock re-rank, guarded edits, outage fallback | 24 | 0 |
| `test_ranking.py` | Brief constraints on every promo, beat-aligned cuts, rank/post order, overlap + episode caps, platform presets, learner | 6 | 0 |
| `test_real_pack.py` |  | 3 | 0 |
| `test_robustness.py` | 12 layout mutations, wrong/missing extensions, HTML/ODT, no timestamps, garbage, fallback reader, min-score relaxation, failing stage, failing export, corrupt config, bad regex, LLM fallback chain, circuit breaker | 25 | 0 |
| `test_timecode.py` | Every timestamp format (mm:ss, hh:mm:ss, SRT, SMPTE frames, 1m23s), formatting | 18 | 0 |

## 2. Which metrics matter for a promo finder (and why)

| Metric | Definition | Why it matters | Target |
|---|---|---|---|
| **Recall vs. editor** | Share of the editor's manual promos the tool also returns (time IoU ≥ 0.30 or ≥ 50% coverage) | The tool replaces an editor's pass; if it misses what they would post, it is not trusted | ≥ 70% overall, ≥ 50% in top 10 |
| **Recall@10** | Same, counting only the tool's top 10 | Editors review the top of the list first | ≥ 50% |
| **Cut-point error** | Mean \|Δstart\| and \|Δend\| in seconds on matched promos | Every second an editor re-trims is time the tool did not save | ≤ 5 s |
| **Hook ≤ 3 s** | Promo has a hook cue (≥ 0.4) that lands within 3 s of IN | Brief requirement #1 — the scroll-stop | 100% |
| **Strong cliffhanger** | Cliffhanger score ≥ 0.5 at OUT | Brief requirement #2 — drives the tap-through | ≥ 85% |
| **Stand-alone** | No `needs_context` flag (pronoun/back-reference/off-screen-name penalties) | Brief requirement #3 — new viewers | ≥ 85% |
| **Length compliance** | 20–60 s (or the platform preset) | Hard platform/brief constraint | 100% |
| **Diversity** | Distinct episodes and tropes in the top 10 | A week of posts should test different angles | ≥ 5 episodes |
| **Flagged share** | Promos with any quality warning | How much human review is still needed | trend ↓ |
| **Runtime & cost / show** | Seconds and LLM tokens per 50-episode show | Kuku releases shows weekly; must be ~free at volume | < 10 s rules; < $0.10 LLM |
| **Timestamp coverage** | Share of beats with explicit timestamps | Low coverage = interpolated IN/OUT points | ≥ 95% |

## 3. Results on the sample show (rules only, no API key)

8 episodes · 211 beats · 100% timestamped · 101 candidates scored → **15 promos** (2 stitched) in **0.35 s**.

| Brief requirement | Result |
|---|---:|
| Length 20–60 s | 100% |
| Hook within first 3 s | 100% |
| Strong cliffhanger at the cut | 93% |
| Stands on its own | 100% |
| **All three at once** | **93%** |

Diversity: 7 episodes and 6 tropes in the top 10; 100% of episodes have at least one promo. Mean score 72.7 (top 10: 77.0); 60% of promos carry a warning flag.

**Top 5 as ranked:**

| Rank | Post | Cut | Hook | Cliffhanger | Score |
|---:|---:|---|---|---|---:|
| 1 | 1 | Ep 1 00:50.0–01:37.0 | Shocking line: CHLOE: Regret? You're nothing. A nobody who scrubs our toile | Writer-marked cliffhanger | 83 |
| 2 | 2 | Ep 3 00:43.0–01:40.0 | Physical shock: (A guard grabs Ava's wrist. She doesn't move.) | Reveal about to land | 82 |
| 3 | 9 | Ep 8 01:03.0–01:27.0 | Reveal: (Chloe enters holding a paternity test envelope.) | Writer-marked cliffhanger | 82 |
| 4 | 6 | Ep 4 01:14.0–01:36.0 | Shocking line: CHLOE: How dare you show your face here! | Someone/something arrives | 82 |
| 5 | 3 | Ep 2 00:50.0–01:07.0 + Ep 3 01:27.0–01:40.0 | Reveal: (A guard empties Ava's apron pocket. A diamond ring falls on | Reveal about to land | 79 |

## 4. Agreement with manual promos (sample)

**The tool found 10 of your 10 manual promos.**

| Metric | Value |
|---|---:|
| Recall (found / manual) | 100% (10/10) |
| Recall incl. partial overlaps | 100% |
| Recall@5 / @10 | 40% / 90% |
| Precision vs. manual (tool promos that match one of yours) | 67% |
| Mean IoU of matches | 0.64 |
| Mean \|Δstart\| / \|Δend\| | 12.7 s / 4.11 s |
| Hook agreement (tool hook inside your first 3 s ± 3 s) | 20% |
| New finds (tool promos not on the manual list) | 5 |

| Manual | Status | Tool | IoU | Δstart | Δend | Diagnosis |
|---|---|---|---:|---:|---:|---|
| M1 | matched | P06 #6 | 0.75 | 7.0 | -5.0 | Found. Boundaries differ by more than 5 s. |
| M2 | matched | P01 #1 | 0.38 | 14.0 | 2.0 | Found. Boundaries differ by more than 5 s. |
| M3 | matched | P07 #7 | 0.69 | 32.0 | -15.0 | Found. Boundaries differ by more than 5 s. |
| M4 | matched | P10 #10 | 0.37 | -15.0 | — | Found. Boundaries differ by more than 5 s. |
| M5 | matched | P13 #13 | 0.69 | -4.0 | -6.0 | Found. Boundaries differ by more than 5 s. |
| M6 | matched | P04 #4 | 0.59 | 8.0 | -7.0 | Found. Boundaries differ by more than 5 s. |
| M7 | matched | P09 #9 | 0.70 | -12.0 | 0.0 | Found. Boundaries differ by more than 5 s. |
| M8 | matched | P08 #8 | 0.96 | 0.0 | 1.0 | Found. |
| M9 | matched | P14 #14 | 0.40 | -31.0 | -1.0 | Found. Boundaries differ by more than 5 s. |
| M10 | matched | P03 #3 | 0.86 | 4.0 | 0.0 | Found. |

Precision vs. manual is low by design: the editor listed 10 promos, the tool returns more. "New finds" are not errors; they are candidates the editor did not shortlist.

## 5. Ablation — what each signal contributes (sample, vs. manual promos)

| Variant | Recall | Recall@5 | Recall@10 | Mean IoU | All-three compliance | Episodes in top 10 |
|---|---:|---:|---:|---:|---:|---:|
| Full scorer (default weights) | 100% | 40% | 90% | 0.64 | 93% | 7 |
| Without hook signal | 90% | 30% | 60% | 0.612 | 60% | 6 |
| Without cliffhanger signal | 90% | 50% | 90% | 0.654 | 62% | 7 |
| Without stand-alone check | 100% | 40% | 70% | 0.605 | 93% | 6 |
| Without diversity (pure score order) | 100% | 40% | 90% | 0.64 | 94% | 7 |
| Without stitched promos | 100% | 50% | 80% | 0.63 | 86% | 7 |
| Hook + cliffhanger only | 100% | 30% | 80% | 0.603 | 88% | 8 |

Read this as: if removing a signal does not change recall on the sample, the sample is too small to show its value. Re-run on the real 50 episodes and your picks to see which weights earn their place, then `promo-finder learn`.

## 6. Parser robustness (input format is unknown in advance)

| Input layout | Episodes expected | Found | Beats | Dialogue lines with speaker | Timestamped |
|---|---:|---:|---:|---:|---:|
| Bracketed `[00:00:07] NAME: line`, 2 episodes in one file | 2 | 2 ✅ | 8 | 5 | 100% |
| Pipe table with header row and ranges | 1 | 1 ✅ | 3 | 2 | 100% |
| Classic layout (TC line / NAME / (paren) / dialogue) | 1 | 1 ✅ | 3 | 2 | 100% |
| Lines without timestamps (interpolated) | 1 | 1 ✅ | 4 | 4 | 50% |
| Show-absolute timestamps (shifted to 0) | 1 | 1 ✅ | 2 | 2 | 100% |
| Two episodes, no headers, clock resets | 2 | 2 ✅ | 5 | 5 | 100% |
| Subtitles (.srt) | 1 | 1 ✅ | 2 | 2 | 100% |
| Sample: .txt bracketed (3 files) | 3 | 3 ✅ | 81 | 46 | 100% |
| Sample: .docx with untagged actions | 1 | 1 ✅ | 26 | 14 | 100% |
| Sample: PDF, 2 episodes, running header + page numbers | 2 | 2 ✅ | 48 | 30 | 100% |
| Sample: full zip with nested zip + __MACOSX junk | 8 | 8 ✅ | 211 | 120 | 100% |
| Kuku block layout (synthetic fixture): **LABEL (manner):** / Start–End line / text, metadata header, overlapping shots | 2 | 2 ✅ | 23 | 12 | 100% |
| **Real input pack** (data/input) | 50 | 50 ✅ | 3727 | 1487 | 100% |

## 7. Scale and cost

**50-episode show** (sample episodes cycled to 50, 1319 beats, 78.45 min of screen time): rules-only pipeline median **1.64 s** over 3 runs (33 ms per episode), 589 candidates scored → 30 promos. Memory: tens of MB.

**LLM re-rank cost** (measured prompt sizes for this 50-episode run, top 30 candidates, 6 calls):
≈ 10,985 input + 3,300 output tokens per show.

| Provider tier | Cost per show | Cost for 52 shows/year |
|---|---:|---:|
| Gemini / Groq / OpenRouter free tiers | $0 (within free daily limits) | $0 |
| Small paid model (~$0.15 / $0.60 per 1M tokens) | $0.004 | $0.19 |
| Mid model (~$1 / $4 per 1M) | $0.024 | $1.26 |
| Frontier model (~$3 / $15 per 1M) | $0.082 | $4.29 |

Prices are illustrative list-price bands for budgeting, not quotes; check the provider's page. Repeated runs on the same show cost $0 (disk cache keyed on provider + model + prompt).

## 8. Where it picks badly (observed on the sample)

- **P02** (Ep 3 00:43.0–01:40.0) — flags: visual_hook. Hook: _(A guard grabs Ava's wrist. She doesn't move.)_
- **P03** (Ep 8 01:03.0–01:27.0) — flags: spoiler_risk. Hook: _(Chloe enters holding a paternity test envelope.)_
- **P05** (Ep 2 00:50.0–01:07.0 + Ep 3 01:27.0–01:40.0) — flags: jump_cuts. Hook: _(A guard empties Ava's apron pocket. A diamond ring falls onto the cou_
- **P07** (Ep 2 01:07.0–01:11.0 + Ep 2 00:30.0–01:07.0) — flags: jump_cuts, visual_hook. Hook: _(Two guards grab Ava by the arms and drag her toward the door.)_
- **P08** (Ep 6 00:00.0–00:28.0) — flags: spoiler_risk, visual_hook. Hook: _(A hooded figure lunges from the balcony and grabs Ava by the throat.)_
- **P10** (Ep 2 01:07.0–01:39.5) — flags: soft_ending, visual_hook. Hook: _(Two guards grab Ava by the arms and drag her toward the door.)_

- Cut points drift ~5–15 s from the editor's: the tool trims to the hook line, while editors often keep a few seconds of set-up before it. Use the **long** variant (shown per promo) when you want that set-up.
- Visual-only beats (a look, a silent reveal) and sarcasm are invisible to the rules; the optional LLM judge re-scores the top candidates to catch these.
