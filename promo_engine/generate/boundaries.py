"""Start/end refinement and tight / standard / long cut variants.

Rules (all snap to whole beats, never cross the episode edge):
- Trim dead air before the hook if the clip stays >= min length and the score improves.
- tight    = shortest clip (>= min length) that still ends on the same cliffhanger.
- long     = longest clip (<= max length) ending on the same cliffhanger, preferring a scene start.
"""
from __future__ import annotations

from ..models import Episode, Segment, Show
from .candidates import Candidate, window_features


def refine(c: Candidate, show: Show, cfg: dict, lex, scorer) -> Candidate:
    if c.kind != "continuous":
        return c
    seg = c.segments[0]
    ep = show.episode(seg.episode)
    hb = c.features.get("hook_beat")
    lo = float(cfg["promo"]["min_seconds"])
    if hb is not None and hb > seg.first_beat:
        dur = ep.span_end(hb, seg.last_beat) - ep.beats[hb].start
        if dur >= lo:
            f = window_features(show, ep, hb, seg.last_beat, cfg, lex)
            alt = Candidate(segments=[Segment(ep.number, ep.beats[hb].start, ep.span_end(hb, seg.last_beat), hb, seg.last_beat)],
                            features=f)
            scorer(alt)
            if alt.score >= c.score:
                alt.features["refined"] = f"trimmed {ep.beats[hb].start - seg.start:.1f}s of lead-in so the hook lands at 0s"
                return alt
    return c


def _content_idx(ep: Episode, i: int, step: int):
    while 0 <= i < len(ep.beats) and ep.beats[i].kind == "scene":
        i += step
    return i if 0 <= i < len(ep.beats) else None


def variants(c: Candidate, show: Show, cfg: dict) -> dict[str, dict]:
    def pack(ep, i, j):
        e = ep.span_end(i, j)
        return {"episode": ep.number, "start": round(ep.beats[i].start, 3), "end": round(e, 3),
                "first_beat": i, "last_beat": j, "duration": round(e - ep.beats[i].start, 2)}

    if c.kind != "continuous":
        seg = c.segments[0]
        ep = show.episode(seg.episode)
        return {"standard": pack(ep, seg.first_beat, seg.last_beat)}
    seg = c.segments[0]
    ep = show.episode(seg.episode)
    lo, hi = float(cfg["promo"]["min_seconds"]), float(cfg["promo"]["max_seconds"])
    j = seg.last_beat
    end = seg.end
    out = {"standard": pack(ep, seg.first_beat, j)}
    # tight: move start forward as far as possible while >= lo
    tight_i = seg.first_beat
    for i in range(seg.first_beat, j + 1):
        if ep.beats[i].kind == "scene":
            continue
        if end - ep.beats[i].start >= lo:
            tight_i = i
        else:
            break
    # prefer a beat with a hook near the tight start
    for i in range(tight_i, seg.first_beat - 1, -1):
        if ep.beats[i].signals.get("hook", 0) >= 0.5 and end - ep.beats[i].start <= hi:
            tight_i = i
            break
    out["tight"] = pack(ep, tight_i, j)
    # long: move start back while <= hi; prefer a scene start
    long_i = seg.first_beat
    best_scene = None
    for i in range(seg.first_beat - 1, -1, -1):
        if end - ep.beats[i].start > hi:
            break
        if ep.beats[i].kind == "scene":
            nxt = _content_idx(ep, i, 1)
            if nxt is not None:
                best_scene = nxt
            continue
        long_i = i
    if best_scene is not None and end - ep.beats[best_scene].start <= hi:
        long_i = best_scene
    out["long"] = pack(ep, long_i, j)
    return out
