"""Run-level metrics: the numbers that matter for a promo finder.

Brief compliance  : duration in 20–60 s, hook inside first 3 s, ends on a cliffhanger.
Usefulness        : stand-alone score, diversity (episodes / tropes covered), editor-ready timestamps.
Agreement         : recall vs. the editor's manual promos (see compare.py).
Operations        : runtime per stage, LLM calls / tokens, cost per show.
Input health      : share of lines with explicit timestamps.
"""
from __future__ import annotations

from statistics import mean, median

from ..models import Promo, Show


def run_metrics(show: Show, promos: list[Promo], pool_size: int, timings: dict, llm_report: dict | None, cfg: dict) -> dict:
    lo, hi = float(cfg["promo"]["min_seconds"]), float(cfg["promo"]["max_seconds"])
    hw = float(cfg["promo"]["hook_window_seconds"])
    n = len(promos) or 1
    content_beats = sum(1 for e in show.episodes for b in e.beats if b.kind != "scene")
    timed = sum(1 for e in show.episodes for b in e.beats if b.kind != "scene" and b.timed)
    top10 = sorted(promos, key=lambda p: p.rank)[:10]
    tropes10 = {t for p in top10 for t in p.tropes[:1]}
    durations = [p.duration for p in promos]
    tokens_in = (llm_report or {}).get("stats", {}).get("input_tokens", 0)
    tokens_out = (llm_report or {}).get("stats", {}).get("output_tokens", 0)
    total_runtime = sum(v for v in timings.values())
    return {
        "input": {
            "episodes": len(show.episodes),
            "beats": content_beats,
            "scenes": sum(len(e.scenes) for e in show.episodes),
            "characters": len(show.characters),
            "show_minutes": round(show.total_seconds / 60, 2),
            "timestamp_coverage": round(timed / content_beats, 3) if content_beats else None,
            "warnings": len(show.warnings) + sum(len([w for w in e.warnings if not w.startswith('offset=')]) for e in show.episodes),
        },
        "output": {
            "candidates_scored": pool_size,
            "promos": len(promos),
            "montages": sum(1 for p in promos if len(p.segments) > 1),
            "duration_median_s": round(median(durations), 1) if durations else None,
            "duration_min_s": round(min(durations), 1) if durations else None,
            "duration_max_s": round(max(durations), 1) if durations else None,
        },
        "brief_compliance": {
            "duration_in_range": round(sum(lo - 0.5 <= p.duration <= hi + 0.5 for p in promos) / n, 3),
            "hook_within_3s": round(sum(p.hook.get("at", 99) <= hw and p.hook.get("score", 0) >= 0.4 for p in promos) / n, 3),
            "strong_cliffhanger": round(sum(p.cliffhanger.get("score", 0) >= 0.5 for p in promos) / n, 3),
            "standalone_ok": round(sum(p.breakdown.get("standalone", 0) > 0 and "needs_context" not in p.flags for p in promos) / n, 3),
            "all_three": round(sum(p.hook.get("at", 99) <= hw and p.hook.get("score", 0) >= 0.4 and p.cliffhanger.get("score", 0) >= 0.5
                                   and "needs_context" not in p.flags for p in promos) / n, 3),
        },
        "quality": {
            "mean_score": round(mean(p.score for p in promos), 1) if promos else None,
            "top10_mean_score": round(mean(p.score for p in top10), 1) if top10 else None,
            "mean_hook": round(mean(p.hook.get("score", 0) for p in promos), 3) if promos else None,
            "mean_cliffhanger": round(mean(p.cliffhanger.get("score", 0) for p in promos), 3) if promos else None,
            "flagged_share": round(sum(1 for p in promos if p.flags) / n, 3),
        },
        "diversity": {
            "episodes_in_top10": len({e for p in top10 for e in p.episodes}),
            "tropes_in_top10": len(tropes10),
            "episodes_covered": len({e for p in promos for e in p.episodes}),
            "episode_coverage": round(len({e for p in promos for e in p.episodes}) / max(1, len(show.episodes)), 3),
        },
        "operations": {
            "runtime_s": round(total_runtime, 3),
            "stage_seconds": {k: round(v, 3) for k, v in timings.items()},
            "seconds_per_episode": round(total_runtime / max(1, len(show.episodes)), 4),
            "llm": {
                "used": bool(llm_report),
                "provider": (llm_report or {}).get("provider"),
                "model": (llm_report or {}).get("model"),
                "calls": (llm_report or {}).get("stats", {}).get("calls", 0),
                "cache_hits": (llm_report or {}).get("stats", {}).get("cache_hits", 0),
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "judged": (llm_report or {}).get("judged", 0),
                "failed_batches": (llm_report or {}).get("failed_batches", 0),
                "boundary_edits": (llm_report or {}).get("edits", 0),
            },
        },
    }
