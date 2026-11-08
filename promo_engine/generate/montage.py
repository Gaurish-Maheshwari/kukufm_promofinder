"""Multi-segment promos.

A) Cold open (within one episode): open on the episode's biggest hook moment
   (a 3–8 s flash-forward), then jump back to the build-up and cut right
   before that moment lands.
B) Escalation supercut (across episodes): 2–3 short moments that share a main
   character, in story order, starting on a hook and ending on a cliffhanger.

Both are scored with exactly the same scorer as continuous promos, with a
stand-alone penalty for every jump so they only win when they are clearly better.
"""
from __future__ import annotations

from itertools import combinations

from ..analysis.characters import characters_in
from ..analysis.lexicon import Lexicon
from ..models import Episode, Segment, Show
import math

from .candidates import Candidate, cliff_features, window_features

JUMP_PENALTY = 0.08


def _short_moment(ep: Episode, h: int, min_len: float, max_len: float):
    """Best window starting at beat h with min_len <= dur <= max_len, maximising the end cliff."""
    best = None
    for j in range(h, len(ep.beats)):
        if ep.beats[j].kind == "scene":
            continue
        dur = ep.span_end(h, j) - ep.beats[h].start
        if dur > max_len:
            break
        if dur < min_len:
            continue
        cf = cliff_features(ep, h, j)
        if best is None or cf["cliffhanger"] > best[1]["cliffhanger"]:
            best = (j, cf)
    return best


def _combine(show: Show, parts: list[tuple[Episode, int, int]], cfg: dict, lex: Lexicon, kind: str) -> Candidate:
    feats = [window_features(show, ep, i, j, cfg, lex) for ep, i, j in parts]
    segs = [Segment(ep.number, ep.beats[i].start, ep.span_end(i, j), i, j) for ep, i, j in parts]
    dur = sum(s.duration for s in segs)
    f = dict(feats[-1])  # cliff-related fields come from the last segment
    first = feats[0]
    for k in ("hook", "hook_beat", "hook_at", "hook_type"):
        f[k] = first[k]
    n = len(parts)
    f["intensity"] = round(sum(x["intensity"] for x in feats) / n, 4)
    f["pace"] = round(sum(x["pace"] for x in feats) / n, 4)
    f["trope"] = max(x["trope"] for x in feats)
    f["tropes"] = list(dict.fromkeys(t for x in feats for t in x["tropes"]))
    f["standalone"] = round(max(0.0, min(x["standalone"] for x in feats) - JUMP_PENALTY * (n - 1)), 4)
    f["standalone_reasons"] = [r for x in feats for r in x["standalone_reasons"]] + [f"{n - 1} jump cut(s) between moments"]
    f["spoiler"] = max(x["spoiler"] for x in feats)
    f["timing_confidence"] = min(x["timing_confidence"] for x in feats)
    target = float(cfg["promo"]["target_seconds"])
    f["duration_fit"] = round(math.exp(-((dur - target) / 15.0) ** 2), 4)
    f["duration"] = round(dur, 2)
    f["hook_segment"] = 0
    return Candidate(segments=segs, kind=kind, features=f)


def cold_open_montages(show: Show, cfg: dict, lex: Lexicon, scorer, pool: list[Candidate]) -> list[Candidate]:
    lo, hi = float(cfg["promo"]["min_seconds"]), float(cfg["promo"]["max_seconds"])
    out = []
    by_ep: dict[int, list[Candidate]] = {}
    for c in pool:
        if c.kind == "continuous":
            by_ep.setdefault(c.segments[0].episode, []).append(c)
    for ep in show.episodes:
        hooks = sorted((b for b in ep.beats if b.signals.get("hook", 0) >= 0.75), key=lambda b: -b.signals["hook"])[:2]
        for hb in hooks:
            mom = _short_moment(ep, hb.idx, 2.5, 8.0)
            if not mom:
                continue
            hj = mom[0]
            for body in by_ep.get(ep.number, []):
                s = body.segments[0]
                if s.last_beat >= hb.idx or hb.start - s.end > 4.0:
                    continue  # body must lead right up to the hook moment
                total = s.duration + (ep.span_end(hb.idx, hj) - hb.start)
                if not (lo <= total <= hi):
                    continue
                c = _combine(show, [(ep, hb.idx, hj), (ep, s.first_beat, s.last_beat)], cfg, lex, "montage_episode")
                scorer(c)
                out.append(c)
    out.sort(key=lambda c: -c.score)
    return out[:4]


def escalation_supercuts(show: Show, cfg: dict, lex: Lexicon, scorer, max_gap_eps: int = 6) -> list[Candidate]:
    lo, hi = float(cfg["promo"]["min_seconds"]), float(cfg["promo"]["max_seconds"])
    main = {n for n, r in show.characters.items() if r.get("main")}
    moments = []
    for ep in show.episodes:
        tops = sorted((b for b in ep.beats if b.signals.get("hook", 0) >= 0.7), key=lambda b: -b.signals["hook"])[:2]
        for hb in tops:
            m = _short_moment(ep, hb.idx, 6.0, 20.0)
            if m:
                present, _ = characters_in(ep.beats[hb.idx:m[0] + 1])
                moments.append((ep, hb.idx, m[0], m[1]["cliffhanger"], present & main))
    out = []
    for size in (2, 3):
        for combo in combinations(moments, size):
            eps = [m[0].number for m in combo]
            if len(set(eps)) < size or eps != sorted(eps) or eps[-1] - eps[0] > max_gap_eps:
                continue
            shared = set.intersection(*[m[4] for m in combo]) if all(m[4] for m in combo) else set()
            if not shared:
                continue
            total = sum(m[0].span_end(m[1], m[2]) - m[0].beats[m[1]].start for m in combo)
            if not (lo <= total <= hi) or combo[-1][3] < 0.4:
                continue
            c = _combine(show, [(m[0], m[1], m[2]) for m in combo], cfg, lex, "montage_cross")
            c.features["shared_characters"] = sorted(shared)
            scorer(c)
            out.append(c)
    out.sort(key=lambda c: -c.score)
    return out[:6]


def generate_montages(show: Show, cfg: dict, lex: Lexicon, scorer, pool: list[Candidate]) -> list[Candidate]:
    if not cfg["promo"].get("enable_montages", True):
        return []
    res = cold_open_montages(show, cfg, lex, scorer, pool) + escalation_supercuts(show, cfg, lex, scorer)
    res.sort(key=lambda c: -c.score)   # (the montage penalty is applied inside the scorer)
    return res[: int(cfg["promo"].get("max_montages", 8))]
