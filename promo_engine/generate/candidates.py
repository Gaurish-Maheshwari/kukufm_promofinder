"""Candidate generation + window features.

Every promo candidate is a window of whole beats (we never cut mid-line) whose
length sits inside [min_seconds, max_seconds]. For each window we compute the
features the scorer needs. This is the "recall" stage: cheap, exhaustive,
deterministic.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from ..analysis.lexicon import Lexicon
from ..analysis.standalone import standalone_score
from ..models import Episode, Segment, Show


@dataclass
class Candidate:
    segments: list[Segment]
    kind: str = "continuous"
    features: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.segments)

    @property
    def key(self) -> tuple:
        return tuple((s.episode, s.first_beat, s.last_beat) for s in self.segments)


def episode_fraction(show: Show, number: int) -> float:
    nums = [e.number for e in show.episodes]
    if len(nums) <= 1:
        return 0.0
    return nums.index(number) / (len(nums) - 1)


def _next_content(ep: Episode, j: int):
    for b in ep.beats[j + 1:]:
        if b.kind != "scene":
            return b
    return None


def hook_features(ep: Episode, i: int, j: int, hook_window: float) -> dict[str, Any]:
    start = ep.beats[i].start
    best, best_k, best_at = 0.0, None, 0.0
    for k in range(i, j + 1):
        b = ep.beats[k]
        at = b.start - start
        if at > hook_window:
            break
        if b.kind == "scene":
            continue
        v = b.signals.get("hook", 0.0) * (1 - 0.08 * at)
        if v > best:
            best, best_k, best_at = v, k, at
    return {"hook": round(best, 4), "hook_beat": best_k, "hook_at": round(best_at, 2),
            "hook_type": ep.beats[best_k].signals.get("hook_type") if best_k is not None else None}


def cliff_features(ep: Episode, i: int, j: int) -> dict[str, Any]:
    last = ep.beats[j]
    c = last.signals.get("cliff", 0.0)
    ctype = last.signals.get("cliff_type")
    cbeat = j
    if j - 1 >= i and last.duration < 1.5:
        prev = ep.beats[j - 1]
        if 0.8 * prev.signals.get("cliff", 0.0) > c:
            c, ctype, cbeat = 0.8 * prev.signals.get("cliff", 0.0), prev.signals.get("cliff_type"), j - 1
    res = last.signals.get("resolution", 0.0)
    c *= (1 - 0.7 * res)
    nb = _next_content(ep, j)
    tease = 0.0
    if nb is not None and nb.scene_id == last.scene_id:
        tease = nb.signals.get("reveal", 0.0)
        if tease >= 0.6:
            new_c = 1 - (1 - c) * (1 - 0.45 * tease)
            if new_c - c > 0.1 and c < 0.5:
                ctype = "tease_next"
            c = new_c
    ep_end = 1.0 if last.signals.get("is_last") else 0.0
    if ep_end:
        c = 1 - (1 - c) * 0.7
        if ctype is None:
            ctype = "episode_end"
    return {"cliffhanger": round(min(1.0, c), 4), "cliff_type": ctype, "cliff_beat": cbeat,
            "resolution_at_end": round(res, 3), "tease_next": round(tease, 3), "episode_end": ep_end}


def window_features(show: Show, ep: Episode, i: int, j: int, cfg: dict, lex: Lexicon) -> dict[str, Any]:
    pc = cfg["promo"]
    beats = ep.beats[i:j + 1]
    content = [b for b in beats if b.kind != "scene"]
    dur = ep.span_end(i, j) - ep.beats[i].start
    f: dict[str, Any] = {"duration": round(dur, 2)}
    f.update(hook_features(ep, i, j, float(pc["hook_window_seconds"])))
    f.update(cliff_features(ep, i, j))
    ints = sorted((b.signals.get("intensity", 0.0) for b in content), reverse=True)
    top = ints[: max(1, len(ints) // 2)]
    f["intensity"] = round(0.6 * (sum(top) / len(top)) + 0.4 * (ints[0] if ints else 0.0), 4) if ints else 0.0
    rate = len(content) / max(dur, 1e-6) * 10
    gaps = [b2.start - b1.start for b1, b2 in zip(content, content[1:])]
    f["pace"] = round(min(1.0, rate / 4.0) * (0.7 if gaps and max(gaps) > 6 else 1.0), 4)
    target = float(pc["target_seconds"])
    f["duration_fit"] = round(math.exp(-((dur - target) / 15.0) ** 2), 4)
    trope_counts: Counter = Counter()
    for b in content:
        trope_counts.update(b.signals.get("tropes", []))
    f["tropes"] = [t for t, _ in trope_counts.most_common()]
    f["trope"] = round(max((lex.trope_value.get(t, 0.6) * min(1.0, c / 2) for t, c in trope_counts.items()), default=0.0), 4)
    sa, reasons = standalone_score(ep, i, j)
    f["standalone"] = round(sa, 4)
    f["standalone_reasons"] = reasons
    safe = float(cfg.get("schedule", {}).get("spoiler_safe_episode_fraction", 0.4))
    frac = episode_fraction(show, ep.number)
    reveal = max((b.signals.get("reveal", 0.0) for b in content), default=0.0)
    f["spoiler"] = round(max(0.0, (frac - safe) / max(1e-6, 1 - safe)) * (0.5 + 0.5 * reveal), 4)
    f["timing_confidence"] = round(sum(b.timed for b in content) / max(1, len(content)), 3)
    return f


def iou_1d(a: tuple[float, float], b: tuple[float, float]) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def generate_candidates(show: Show, cfg: dict, lex: Lexicon, scorer, warnings: Optional[list] = None) -> list[Candidate]:
    """Exhaustive beat-aligned windows per episode, scored, de-duplicated, top-N kept per episode.
    An episode that fails is skipped with a warning; the others still produce candidates."""
    out: list[Candidate] = []
    for ep in show.episodes:
        try:
            out.extend(_episode_candidates(show, ep, cfg, lex, scorer))
        except Exception as exc:  # noqa: BLE001
            if warnings is not None:
                warnings.append(f"Episode {ep.number}: candidate generation failed ({exc}); episode skipped.")
    return out


def _episode_candidates(show: Show, ep: Episode, cfg: dict, lex: Lexicon, scorer) -> list[Candidate]:
    pc = cfg["promo"]
    lo, hi = float(pc["min_seconds"]), float(pc["max_seconds"])
    keep = int(pc.get("candidates_per_episode", 40))
    out: list[Candidate] = []
    if True:
        beats = ep.beats
        n = len(beats)
        cands: list[Candidate] = []
        for i in range(n):
            if beats[i].kind == "scene":
                continue
            s0 = beats[i].start
            wend = s0
            for j in range(i, n):
                wend = max(wend, beats[j].end)        # beats may overlap: the clip ends at the latest end
                if beats[j].kind == "scene":
                    continue
                if beats[j].start - s0 > hi:
                    break
                dur = wend - s0
                if dur < lo:
                    continue
                if dur > hi:
                    break
                if j + 1 < n and beats[j + 1].start < wend - 0.05 and beats[j + 1].kind != "scene":
                    continue                          # never cut while the next beat is already playing
                f = window_features(show, ep, i, j, cfg, lex)
                c = Candidate(segments=[Segment(ep.number, s0, wend, i, j)], features=f)
                scorer(c)
                cands.append(c)
        if not cands and beats:
            # episode shorter than min_seconds: offer the whole episode, flagged later
            i0 = next((k for k, b in enumerate(beats) if b.kind != "scene"), 0)
            j0 = n - 1
            f = window_features(show, ep, i0, j0, cfg, lex)
            c = Candidate(segments=[Segment(ep.number, beats[i0].start, ep.span_end(i0, j0), i0, j0)], features=f)
            scorer(c)
            cands.append(c)
        cands.sort(key=lambda c: -c.score)
        kept: list[Candidate] = []
        for c in cands:  # light NMS so the pool is not 40 copies of one peak
            span = (c.segments[0].start, c.segments[0].end)
            if all(iou_1d(span, (k.segments[0].start, k.segments[0].end)) < 0.6 for k in kept):
                kept.append(c)
            if len(kept) >= keep:
                break
        out.extend(kept)
    return out


def score_manual_window(show: Show, episode: int, start: float, end: float, cfg: dict, lex: Lexicon, scorer) -> Optional[Candidate]:
    """Snap an arbitrary (episode, start, end) to beats and score it like any candidate.
    Used to explain why a manual promo was (not) picked."""
    ep = show.episode(episode)
    if ep is None or not ep.beats:
        return None
    content = [b for b in ep.beats if b.kind != "scene"]
    first = min(content, key=lambda b: abs(b.start - start))
    last = min((b for b in content if b.idx >= first.idx), key=lambda b: abs(b.end - end), default=first)
    f = window_features(show, ep, first.idx, last.idx, cfg, lex)
    c = Candidate(segments=[Segment(episode, first.start, ep.span_end(first.idx, last.idx), first.idx, last.idx)], features=f)
    scorer(c)
    return c
