# Promo Finder — Kuku AI Generalist Assignment, Problem 1

**[Your name] · [Roll no.] · [Branch]** · Prototype: [Vercel link] · Repo: [GitHub link] · Raw outputs: [Drive link] · Video: [Loom link]

## The problem and why I picked it
An editor watches every episode to pick promo moments, and Kuku ships new shows every week, so promo selection grows linearly with the catalogue. The screenplays already carry a timestamp for every line and action. **Reading is far cheaper than watching**, so the tool reads the screenplays and hands editors exact, ranked cut points. Problem 1 has a checkable output (timestamps) and a clear human baseline to measure against (an editor's own picks).

## Assumptions (full list in ASSUMPTIONS.md)
- Timestamps are per episode and each episode is its own video file. Show-absolute times are shifted. Lines without times are interpolated and flagged, never hidden.
- The layout is never guaranteed, so one tolerant reader handles labels, timings and text in any order (the pack's `**NAME (manner):**` / `Start: … | End: …` / text blocks, bracketed, pipe tables, classic, SRT, CSV/XLSX, multi-episode PDFs/DOCX/HTML), sniffs wrong extensions, and falls back to a structure-agnostic reader when its own output looks broken. Camera shots overlap dialogue, so clips end at the latest end inside the window and never mid-line. Loglines and continuity notes are kept as metadata, not dialogue.
- Promo = 20–60 s, cut only on whole lines. Hook = the strongest hook cue starting ≤ 3 s after IN. Cliffhanger = an unresolved last beat, best when it cuts just before a reveal. Stand-alone = no unexplained pronouns, callbacks or off-screen names.
- Stitched promos are allowed but must clearly beat a single take (0.9× penalty, ≤ 3 per list, shared character).
- A match with an editor's promo = time IoU ≥ 0.30 or ≥ 50% coverage.

## How it works
1. **Ingest and parse (code):** files → episodes → timed beats (speaker, action, scene).
2. **Beat signals (rules):** YAML cue lexicons score each line for hook, cliffhanger, resolution, intensity, context-dependence and microdrama tropes.
3. **Candidates (code):** *every* beat-aligned 20–60 s window, plus cold-open and cross-episode montages.
4. **Score (rules):** an explainable weighted sum (hook .30, cliffhanger .25, stand-alone .15, intensity .12, …, minus spoiler risk), with a per-promo breakdown.
5. **AI judge (optional):** the top 30 go to any LLM as *numbered lines* (5 per call). It scores them like an editor and writes the hook, cliffhanger and why. Its cut changes are snapped back to real lines, **so it cannot invent a timestamp**. Final = ½ rules + ½ LLM. If it fails, the rules result stands.
6. **Select and order:** overlap removal, ≤ 3 per episode, MMR for variety. The **posting plan** leads with spoiler-safe early-episode hooks and alternates tropes to learn which angle converts.
7. **Hand-off:** an editor cut sheet (SMPTE + handles), a CMX3600 EDL for Premiere/Resolve, markers, and an HTML report. A web app (React + FastAPI on Vercel/Docker) and a CLI.

**One key, any model:** set `LLM_API_KEY`. Its prefix picks the provider (Gemini, Groq, OpenAI, Anthropic, OpenRouter, Ollama, any OpenAI-compatible gateway) and the model is discovered from the provider's list. A stronger Kuku-provided model is a key or base-URL change, not a code change.

**Human in the loop:** the editor reviews the top 10 in a 9:16 preview and clicks keep or reject. Those labels and their manual picks retrain the weights (`promo-finder learn`, logistic regression).

## How I know it's good ({{data_label}})
| Brief requirement | Result | | Agreement with editor's picks | Result |
|---|---:|---|---|---:|
| Length 20–60 s | {{length}} | | {{headline}} | |
| Hook within 3 s | {{hook3}} | | Recall / Recall@10 | {{recall}} / {{recall10}} |
| Strong cliffhanger | {{cliff}} | | Mean overlap (IoU) | {{iou}} |
| Stands alone | {{standalone}} | | Cut-point error start / end | {{start_err}} / {{end_err}} |

{{episodes}} episodes, {{beats}} beats (100% timed, 0 parse warnings) → {{promos}} promos in {{runtime}}. 123 automated tests pass, including 12 layout mutations and failure injection (corrupt config, failing stage or export, LLM outage with key fallback and circuit breaker). Compliance above is against the tool's own thresholds; quality against an editor needs manual picks (`--manual`). Top picks: {{top3}}.

**Where it picks badly.** (0) *Keyword-level hooks* on the real pack: `"Poison?"` scores as a physical shock and a "sword" mention as action. The LLM judge re-scores the shortlist for this. (1) *Visual-only beats*, such as a look or a silent reveal: the rules read words, not shots, so hooks that live in the picture get under-scored. (2) *Sarcasm and rhetorical questions* look like resolutions or cliffhangers. (3) *Callbacks* ("like that night") are penalised even when the scene still lands. (4) *Stitched edits* are the most likely misses against an editor. (5) *Start points* land 5–15 s later than an editor's, because the tool trims to the hook line while editors keep set-up, so a "long" variant is offered. Every promo carries flags (weak hook, soft ending, needs backstory, guessed timestamps, spoiler risk), so review effort goes where the risk is.

## Scale and cost
A 50-episode show takes ~1.3 s on one laptop core with rules only, and the work is linear in episodes and parallel across shows. The LLM sees a constant shortlist (~11k input + 3k output tokens per show), which is $0 on free tiers and under $0.10 per show on a frontier model, about $40 a year at 10 shows a week. Re-runs are cached. Next steps at scale: a queue job per show, posting performance (CTR, installs) as training labels, and a vision model on the shortlisted clips only for visual hooks.

## AI tools and one place they got it wrong
I built this with **Claude** ([add your other tools]). It wrote most of the code. I chose the scope, the rules-for-recall / LLM-for-taste split, the matching metric and the ranking principles, and I reviewed every output. **Where it got it wrong:** the first cross-episode montages took the hook from one peak and the cliffhanger from another, beat every real single-take promo, and pushed the obvious best clip (the gala slap) out of the list. Later, adding the LLM step silently dropped the montage penalty during re-scoring. Comparing rules-only and LLM rankings side by side exposed both. The fixes (a penalty inside the scorer, a montage cap, a shared-character rule) are covered by tests.
