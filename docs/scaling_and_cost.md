# Scaling to every show, every week

## Volume assumption

Kuku releases new shows every week. Say **5–10 new shows a week × 50–80 episodes × 1–2 min**, which is 250–800 episodes and 5–25 hours of screen time a week.

## Cost per show (50 episodes)

| Component | Compute | Money |
|---|---|---|
| Rules pipeline (parse, signals, ~12k windows, montages, ranking) | ~1.3 s on one laptop core (measured, `METRICS.md §7`) | $0 |
| LLM judge on the top 30 | 6 calls, ≈ 11k input + 3k output tokens (measured prompt sizes) | $0 on Gemini/Groq/OpenRouter free tiers · ≈ $0.004 on a small paid model · ≈ $0.08 on a frontier model |
| Re-running the same show | Disk cache hit | $0 |
| Hosting | Vercel Hobby / any container | $0 to a few $/month |

**At 10 shows a week, a frontier model costs about $40 a year.** LLM cost scales with `rerank_top_n`, not with show length, because only the shortlist is sent.

## Why it scales

- **Linear in episodes.** Windows are enumerated per episode (≈ beats × 15), so 1,000 episodes take about 25 s on one core. Episodes are independent, so this parallelises trivially (multiprocessing, or one job per show).
- **The LLM sees a constant amount per show.** Raising quality means raising `rerank_top_n` or using a stronger model, a single config value.
- **No per-show setup.** Format detection, episode splitting and character discovery are automatic. Show-specific vocabulary (e.g. werewolf "Alpha/Luna") is a lexicon edit, not code.
- **Stateless API.** Any number of API replicas can sit behind a load balancer. Exports don't need server state.

## What would change at Kuku scale

| Need | Change |
|---|---|
| Hundreds of shows in a batch | `promo-finder run` per show from a queue (Cloud Run Jobs, AWS Batch, or GitHub Actions on a schedule), with outputs written to object storage |
| Results inside existing tools | Push the cut sheet or EDL to the asset manager, or post the top 10 to the marketing team's Slack |
| Better ranking over time | Log which promos were posted and their CTR or installs per view, then feed that into `learn` as labels. Real performance beats editor intuition as ground truth. |
| Multilingual shows | The lexicon is the only English-specific part. Add a lexicon per language, or rely on the LLM judge (top-N only), which is multilingual already. |
| Video-aware hooks (a look, a silent reveal) | Add a vision model on keyframes of the shortlisted clips only. This is where a paid API would earn its cost, and the same top-N pattern keeps it cheap. |
| Stronger model provided by Kuku | Set `LLM_BASE_URL` + `LLM_API_KEY` (+ `LLM_MODEL`). No code change. |

## Where a human stays in the loop

1. **Review the top 10** per show (≈ 5 minutes instead of watching 75–100 minutes).
2. **Keep/reject** clicks become training labels.
3. **Final cut and taste** stay with the editor: music, captions and pacing are out of scope by design.

## How we'd know it worked with a real team

| Signal | Target after 4 weeks |
|---|---|
| Editor time per show for promo selection | −70% (from watching everything to reviewing 10) |
| Share of posted promos that came from the tool's top 10 | > 60% |
| Recall vs. editor picks on new shows (blind) | ≥ 70% |
| Promo performance (CTR / installs per 1k views) of tool-sourced vs. hand-sourced promos | not worse, then better as `learn` uses performance labels |
| Cut-point re-trims needed | median ≤ 3 s |
