"""Weighted, explainable scoring. Every score comes with its breakdown."""
from __future__ import annotations

from typing import Callable

POSITIVE = ["hook", "cliffhanger", "standalone", "intensity", "pace", "duration_fit", "trope", "episode_end"]


def make_scorer(cfg: dict) -> Callable:
    w = cfg["weights"]
    pos_total = sum(float(w.get(k, 0)) for k in POSITIVE) or 1.0
    w_sp = float(w.get("spoiler_penalty", 0))
    lo, hi = float(cfg["promo"]["min_seconds"]), float(cfg["promo"]["max_seconds"])
    mont_pen = float(cfg["promo"].get("montage_penalty", 0.9))

    def score(c) -> float:
        f = c.features
        contrib = {k: float(w.get(k, 0)) * float(f.get(k, 0.0)) / pos_total * 100 for k in POSITIVE}
        contrib["spoiler_penalty"] = -w_sp * float(f.get("spoiler", 0.0)) / pos_total * 100
        total = sum(contrib.values())
        # soft gates: a promo without a hook or a cliffhanger is not a promo
        if f.get("hook", 0) < 0.15:
            total *= 0.85
        if f.get("cliffhanger", 0) < 0.15:
            total *= 0.85
        if not (lo - 0.5 <= c.duration <= hi + 0.5):
            total *= 0.7
        if len(c.segments) > 1:   # stitched promos must be clearly better to win
            before = total
            total *= mont_pen
            contrib["montage_penalty"] = total - before
        c.breakdown = {k: round(v, 2) for k, v in contrib.items()}
        c.score = round(max(0.0, min(100.0, total)), 2)
        return c.score

    return score
