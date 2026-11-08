"""Overlap removal (NMS) + Maximal Marginal Relevance + per-episode cap.

Goal: the top 10 should not be ten cuts of the same slap, nor all from Ep 1.
"""
from __future__ import annotations

from collections import Counter


def promo_iou(a, b) -> float:
    """Temporal IoU across (possibly multi-segment, multi-episode) promos."""
    inter = 0.0
    for sa in a.segments:
        for sb in b.segments:
            if sa.episode == sb.episode:
                inter += max(0.0, min(sa.end, sb.end) - max(sa.start, sb.start))
    union = a.duration + b.duration - inter
    return inter / union if union > 0 else 0.0


def overlap_of_shorter(a, b) -> float:
    inter = 0.0
    for sa in a.segments:
        for sb in b.segments:
            if sa.episode == sb.episode:
                inter += max(0.0, min(sa.end, sb.end) - max(sa.start, sb.start))
    shorter = min(a.duration, b.duration)
    return inter / shorter if shorter > 0 else 0.0


def _main_ep(c) -> int:
    return c.segments[-1].episode


def similarity(a, b) -> float:
    s = 0.5 if _main_ep(a) == _main_ep(b) else 0.0
    ta, tb = set(a.features.get("tropes") or []), set(b.features.get("tropes") or [])
    if ta or tb:
        s += 0.3 * len(ta & tb) / len(ta | tb)
    if a.features.get("hook_type") and a.features.get("hook_type") == b.features.get("hook_type"):
        s += 0.2
    return s


def select_diverse(cands: list, cfg: dict) -> list:
    pc = cfg["promo"]
    top_k = int(pc.get("top_k", 25))
    lam = float(pc.get("mmr_lambda", 0.78))
    nms = float(pc.get("nms_iou", 0.35))
    cap = int(pc.get("max_per_episode", 3))
    min_score = float(pc.get("min_score", 0))
    max_mont = int(pc.get("max_montages_selected", 3))
    pool = [c for c in sorted(cands, key=lambda c: -c.score)[: max(400, top_k * 10)] if c.score >= min_score]
    if not pool:
        return []
    smax = pool[0].score or 1.0
    selected: list = []
    per_ep: Counter = Counter()
    while pool and len(selected) < top_k:
        best, best_val = None, -1e9
        for c in pool:
            if per_ep[_main_ep(c)] >= cap:
                continue
            if len(c.segments) > 1 and sum(len(s.segments) > 1 for s in selected) >= max_mont:
                continue
            if any(promo_iou(c, s) > nms or overlap_of_shorter(c, s) > 0.6 for s in selected):
                continue
            sim = max((similarity(c, s) for s in selected), default=0.0)
            val = lam * (c.score / smax) - (1 - lam) * sim
            if val > best_val:
                best, best_val = c, val
        if best is None:
            break
        selected.append(best)
        per_ep[_main_ep(best)] += 1
        pool.remove(best)
    return selected
