# How AI was used (and where it got it wrong)

> The brief asks: *"tell us which tools you used and one place where they got it wrong."*
> **Edit this file in your own words before submitting.** The entries below are real incidents from building this repo, so you can cite them, but add your own tools and experience.

## Tools

| Tool | Used for |
|---|---|
| Claude (Anthropic) | Planning the feature set, writing most of the code, tests, docs and diagrams, and reviewing outputs |
| _add yours: ChatGPT / Gemini / Cursor / Copilot…_ | _what for_ |
| Mermaid CLI, Playwright | Rendering architecture diagrams and UI screenshots |

## What was given to AI vs. kept as code or rules

| Task | Who does it | Why |
|---|---|---|
| Reading files, parsing timestamps, cutting windows | Code | It must be exact, deterministic and free. LLMs miscount timestamps. |
| Scoring hooks and cliffhangers | Rules (lexicon) + optional LLM | Rules give full recall cheaply and explainably. The LLM adds taste on a shortlist. |
| Writing the hook / cliffhanger / why lines | Templates, or the LLM when a key is set | Templates are always available. The LLM reads better. |
| Choosing cut points | Code (beat boundaries); the LLM may tighten them, but only to real lines | Prevents invented timestamps |
| Final selection | The editor | Taste, brand safety, campaign context |

## Where the AI got it wrong while building (real examples)

1. **Over-eager hook words.** The first cue lexicon treated *"maid"* and *"knees"* as shocking lines. The descriptive action *"Ava, in a maid's uniform, carries a tray"* and the apology *"I owe you an apology. For the knees."* both scored as strong hooks. Fix: those cues now need the insulting construction ("you're nothing but a maid", "on your knees"), and `tests/test_analysis.py::test_false_positive_guards` locks it in.
2. **Montages that cherry-picked.** The first cross-episode montage took its hook from one peak and its cliffhanger from another. It beat every single-take promo and even pushed the obvious best clip (the gala slap) out of the list through overlap removal. Fix: a 0.9× stitching penalty, at most 3 montages, and a shared-character requirement.
3. **A penalty that silently disappeared.** After adding the LLM re-rank, the montage penalty vanished, because re-scoring after the LLM step recomputed the score without it, and stitched promos jumped back to #1 and #2. It was caught by comparing rules-only and mock-LLM rankings side by side. Fix: the penalty now lives inside the scorer itself.
4. **Parser edge cases.** The table header row `TIME | TYPE | CHARACTER | TEXT` was parsed as a line of dialogue, and a PDF's running header (`… — CONFIDENTIAL DRAFT`, only 2 pages so it didn't hit the 3-repeat rule) became an action line in the middle of Episode 8. Both have regression tests now.
5. **Model names go stale.** Hard-coded default model names age quickly. Instead of trusting them, the client asks the provider's `/models` endpoint and picks a match, with the default only as a fallback.

## How hallucinated timestamps are prevented

The LLM never sees or returns timestamps it could invent. It sees numbered lines (`L7 [Ep 4 01:14.0-01:17.0] CHLOE: How dare you…`) and may answer only with line numbers. These are validated (inside the clip, within the length limits) and mapped back to real beat times. Anything else is rejected and counted (`test_llm_boundary_edits_are_guarded`).

## Second round: the real input pack (more places it got it wrong)

6. **Guessing the format wrong.** The first parser was built before the pack existed. On the real layout (`**NAME (manner):**` / `Start: (00:13.50) | End: (00:14.30)` / text) it treated `Start:` as a character called START, turned the episode logline into dialogue, and left about a third of the lines untimed. Fix: a reader that accepts label, timing and text in any order; metadata keys kept as episode metadata; a quality check that switches to a fallback reader when output looks broken. Result: 3,727/3,727 blocks timed.
7. **Fixing one thing broke another.** Teaching the timecode splitter to find `Start: … End: …` anywhere in a line made `Scene start: 00:00.00` look like a beat called "Scene". Caught by the layout-mutation tests.
8. **Genre bias in the lexicon.** The cue words were written for modern billionaire dramas. In a period drama the decisive line, "Because he is marrying me.", scored zero, while every mention of "the Duchess" counted as a status reveal and the adjective "faint" matched the verb "faints". Fix: genre-neutral betrayal/accusation/royalty cues, titles demoted to a weak "status mention", verb-only patterns.
9. **Too-eager fallback.** The first version of the fallback reader beat the main reader on a deliberately half-timed file and silently dropped the untimed lines. Fix: the fallback is used only when the main output shows clear failure signs.
