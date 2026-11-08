"""Posting order: which promo goes out first, and why.

Principles (from how ReelShort / DramaBox run paid + organic promos):
1. Lead with the strongest hook that is spoiler-safe (early episodes), so a
   viewer who taps through lands near the start of the story.
2. Alternate tropes/angles across consecutive posts to learn which angle
   converts (slap vs. hidden identity vs. pregnancy...).
3. Hold back promos that reveal late-season twists until later waves.
"""
from __future__ import annotations

from ..models import Promo, Show
from .explain import TROPE_NAME


def schedule(promos: list[Promo], show: Show, cfg: dict) -> list[Promo]:
    nums = [e.number for e in show.episodes]
    safe_frac = float(cfg.get("schedule", {}).get("spoiler_safe_episode_fraction", 0.4))
    n = len(nums)
    safe_eps = set(nums[: max(1, int(round(n * safe_frac)))]) if n else set()

    def prio(p: Promo) -> float:
        spoiler = p.breakdown.get("spoiler_penalty", 0.0)
        early = 4.0 if p.episodes and p.episodes[0] in nums[:3] else 0.0
        late = -6.0 if p.episodes and not set(p.episodes) <= safe_eps else 0.0
        return p.score + spoiler * 1.5 + early + late

    remaining = sorted(promos, key=lambda p: -prio(p))
    ordered: list[Promo] = []
    while remaining:
        pick = remaining[0]
        if ordered:
            last = ordered[-1]
            for cand in remaining[:4]:
                if prio(remaining[0]) - prio(cand) > 6:
                    break
                same_trope = (cand.tropes[:1] == last.tropes[:1]) and cand.tropes
                same_ep = cand.episodes[:1] == last.episodes[:1]
                if not same_trope and not same_ep:
                    pick = cand
                    break
        remaining.remove(pick)
        ordered.append(pick)

    for k, p in enumerate(ordered, 1):
        p.post_order = k
        reasons = []
        if k == 1:
            reasons.append("strongest spoiler-safe hook in the set")
        if p.hook.get("score", 0) >= 0.8:
            reasons.append(f"{p.hook.get('type', 'hook').lower()} {max(0.0, p.hook.get('at', 0)):.1f}s in")
        if p.episodes and p.episodes[0] in nums[:3]:
            reasons.append(f"from Ep {p.episodes[0]}, so new viewers land at the start of the story")
        elif p.episodes and not set(p.episodes) <= safe_eps:
            reasons.append(f"held for a later wave: comes from Ep {max(p.episodes)} and risks spoiling a twist")
        if k > 1 and p.tropes and ordered[k - 2].tropes[:1] != p.tropes[:1]:
            reasons.append(f"switches angle to {TROPE_NAME.get(p.tropes[0], p.tropes[0])} to test what converts")
        if not reasons:
            reasons.append(f"solid all-rounder (score {p.score:.0f})")
        p.post_rationale = "; ".join(reasons).capitalize() + "."
    return ordered
