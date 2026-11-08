"""Side-by-side comparison: the tool's promos vs. the editor's manual promos.

Matching
- Temporal IoU across segments (episode-aware): |A ∩ B| / |A ∪ B|.
- Coverage: |A ∩ B| / |manual| (did the AI clip contain the editor's moment?).
- A pair is a MATCH when IoU >= 0.30 or coverage >= 0.50 (configurable);
  PARTIAL when they overlap at all; otherwise the manual promo is MISSED.
- One-to-one greedy assignment by IoU (standard for temporal detection metrics).

Diagnosis for every miss: was it never generated (length/montage), or
generated but out-ranked? We re-score the editor's own window with the same
scorer to show *which* feature pulled it down.
"""
from __future__ import annotations

from typing import Optional

from ..generate.candidates import score_manual_window
from ..models import Promo
from .manual import ManualPromo

FEATURE_LABEL = {"hook": "hook", "cliffhanger": "cliffhanger", "standalone": "stand-alone clarity",
                 "intensity": "intensity", "pace": "pace", "duration_fit": "length fit", "trope": "trope"}


def _inter(msegs, asegs) -> float:
    t = 0.0
    for e1, s1, t1 in msegs:
        for e2, s2, t2 in asegs:
            if e1 == e2:
                t += max(0.0, min(t1, t2) - max(s1, s2))
    return t


def _segs(p: Promo) -> list[tuple[int, float, float]]:
    return [(s.episode, s.start, s.end) for s in p.segments]


def overlap_stats(m: ManualPromo, p: Promo) -> dict:
    a = _segs(p)
    inter = _inter(m.segments, a)
    dm = m.duration
    da = sum(e - s for _, s, e in a)
    union = dm + da - inter
    return {"iou": inter / union if union > 0 else 0.0, "coverage": inter / dm if dm > 0 else 0.0, "inter": inter}


def _greedy(manual: list[ManualPromo], ai: list[Promo], cfg: dict) -> dict[str, tuple[Promo, dict]]:
    ev = cfg.get("evaluation", {})
    t_iou, t_cov = float(ev.get("match_iou", 0.3)), float(ev.get("match_coverage", 0.5))
    pairs = []
    for m in manual:
        for p in ai:
            st = overlap_stats(m, p)
            if st["inter"] > 0:
                pairs.append((st["iou"] + 0.25 * st["coverage"], m, p, st))
    pairs.sort(key=lambda t: -t[0])
    used_m, used_a, out = set(), set(), {}
    for _, m, p, st in pairs:
        if m.id in used_m or p.id in used_a:
            continue
        if st["iou"] >= t_iou or st["coverage"] >= t_cov:
            out[m.id] = (p, st)
            used_m.add(m.id)
            used_a.add(p.id)
    return out


def compare(ai: list[Promo], manual: list[ManualPromo], show, cfg: dict, lex=None, scorer=None,
            pool: Optional[list] = None) -> dict:
    ev = cfg.get("evaluation", {})
    hook_tol = float(ev.get("hook_tolerance_seconds", 3.0))
    lo, hi = float(cfg["promo"]["min_seconds"]), float(cfg["promo"]["max_seconds"])
    ai_sorted = sorted(ai, key=lambda p: p.rank or 999)
    matches = _greedy(manual, ai_sorted, cfg)
    pool_sorted = sorted(pool or [], key=lambda c: -c.score)
    rows = []
    starts, ends, ious, hook_hits = [], [], [], []
    for m in manual:
        row = {"manual": m.to_dict(), "status": "missed", "ai": None, "iou": 0.0, "coverage": 0.0,
               "start_delta": None, "end_delta": None, "hook_agrees": None, "diagnosis": ""}
        if m.id in matches:
            p, st = matches[m.id]
            row.update(status="matched", ai={"id": p.id, "rank": p.rank, "score": p.score,
                                              "segments": [{"episode": s.episode, "start": s.start, "end": s.end} for s in p.segments]},
                       iou=round(st["iou"], 3), coverage=round(st["coverage"], 3))
            if p.segments[0].episode == m.segments[0][0]:
                row["start_delta"] = round(p.segments[0].start - m.segments[0][1], 2)
            if p.segments[-1].episode == m.segments[-1][0]:
                row["end_delta"] = round(p.segments[-1].end - m.segments[-1][2], 2)
            hook_t = p.hook.get("timestamp")
            ep0, ms, _ = m.segments[0]
            row["hook_agrees"] = bool(hook_t is not None and p.hook.get("episode") == ep0 and ms - hook_tol <= hook_t <= ms + 3 + hook_tol)
            if row["start_delta"] is not None:
                starts.append(abs(row["start_delta"]))
            if row["end_delta"] is not None:
                ends.append(abs(row["end_delta"]))
            ious.append(st["iou"])
            hook_hits.append(row["hook_agrees"])
            row["diagnosis"] = "Found." + (" Boundaries differ by more than 5 s." if (abs(row["start_delta"] or 0) > 5 or abs(row["end_delta"] or 0) > 5) else "")
        else:
            best = max(((overlap_stats(m, p), p) for p in ai_sorted), key=lambda t: t[0]["iou"], default=None)
            if best and best[0]["inter"] > 0:
                st, p = best
                row.update(status="partial", ai={"id": p.id, "rank": p.rank, "score": p.score,
                                                  "segments": [{"episode": s.episode, "start": s.start, "end": s.end} for s in p.segments]},
                           iou=round(st["iou"], 3), coverage=round(st["coverage"], 3))
            row["diagnosis"] = diagnose(m, show, cfg, lex, scorer, pool_sorted, lo, hi, row["status"])
        rows.append(row)

    matched_ai = {r["ai"]["id"] for r in rows if r["status"] == "matched"}
    new_finds = [{"id": p.id, "rank": p.rank, "score": p.score, "episodes": p.episodes,
                  "segments": [{"episode": s.episode, "start": s.start, "end": s.end} for s in p.segments],
                  "hook": p.hook.get("text", ""), "why": p.why} for p in ai_sorted if p.id not in matched_ai]
    n = len(manual)
    recall_at = {}
    for k in (5, 10, 20, len(ai_sorted)):
        sub = [p for p in ai_sorted if (p.rank or 999) <= k]
        recall_at[str(k)] = round(len(_greedy(manual, sub, cfg)) / n, 3) if n else None
    matched = sum(r["status"] == "matched" for r in rows)
    partial = sum(r["status"] == "partial" for r in rows)
    man_eps = {e for m in manual for e, _, _ in m.segments}
    ai_eps = {e for p in ai_sorted for e in p.episodes}
    summary = {
        "manual_total": n,
        "matched": matched,
        "partial": partial,
        "missed": n - matched - partial,
        "recall": round(matched / n, 3) if n else None,
        "recall_incl_partial": round((matched + partial) / n, 3) if n else None,
        "precision_vs_manual": round(matched / len(ai_sorted), 3) if ai_sorted else None,
        "recall_at_k": recall_at,
        "mean_iou_matched": round(sum(ious) / len(ious), 3) if ious else None,
        "mean_abs_start_error_s": round(sum(starts) / len(starts), 2) if starts else None,
        "mean_abs_end_error_s": round(sum(ends) / len(ends), 2) if ends else None,
        "hook_agreement": round(sum(hook_hits) / len(hook_hits), 3) if hook_hits else None,
        "episode_coverage": round(len(man_eps & ai_eps) / len(man_eps), 3) if man_eps else None,
        "ai_new_finds": len(new_finds),
        "headline": f"The tool found {matched} of your {n} manual promos" + (f" (+{partial} partial overlap{'s' if partial != 1 else ''})" if partial else "") + ".",
    }
    return {"summary": summary, "rows": rows, "new_finds": new_finds}


def diagnose(m: ManualPromo, show, cfg, lex, scorer, pool_sorted, lo, hi, status) -> str:
    eps = {e for e, _, _ in m.segments}
    if len(m.segments) > 1 or len(eps) > 1:
        return (f"Multi-segment promo ({len(m.segments)} parts, eps {sorted(eps)}). The tool builds only a few "
                "montages per show, so stitched edits are its weakest area.")
    if m.duration < lo - 1 or m.duration > hi + 1:
        return f"Length {m.duration:.0f}s is outside the {lo:.0f}–{hi:.0f}s window the tool searches."
    ep, s, e = m.segments[0]
    if show is None or show.episode(ep) is None:
        return f"Episode {ep} was not found in the input."
    if lex is None or scorer is None:
        return "Not found in the selected promos."
    c = score_manual_window(show, ep, s, e, cfg, lex, scorer)
    if c is None:
        return "Could not align this window to the screenplay."
    rank_in_pool = 1 + sum(1 for x in pool_sorted if x.score > c.score)
    f = c.features
    weakest = sorted(((FEATURE_LABEL[k], f.get(k, 0.0)) for k in FEATURE_LABEL), key=lambda t: t[1])[:2]
    weak_txt = ", ".join(f"{name} {val:.2f}" for name, val in weakest)
    in_pool = any(x.segments[0].episode == ep and x.kind == "continuous" and
                  max(0, min(x.segments[0].end, e) - max(x.segments[0].start, s)) / max(1e-6, max(x.segments[0].end, e) - min(x.segments[0].start, s)) >= 0.3
                  for x in pool_sorted)
    where = "was in the candidate pool but lost to higher-scoring or overlapping picks" if in_pool else "was out-ranked before the final cut"
    return (f"Tool scores your window {c.score:.0f}/100 (≈ #{rank_in_pool} of {len(pool_sorted)} candidates) and it {where}. "
            f"Weakest signals: {weak_txt}." + (" Hook beat is visual/implicit — rules can't see it in text." if f.get('hook', 0) < 0.3 else ""))
