"""LLM re-ranking of the best heuristic candidates.

Rules find candidates cheaply and exhaustively (recall); the LLM reads only the
top N and judges them like an editor would (precision). If the LLM fails for
any reason, the heuristic ranking is kept — the tool never stops working.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from ..generate.candidates import Candidate, window_features
from ..models import Segment, Show
from ..timecode import fmt
from .prompts import CANDIDATE_TEMPLATE, SYSTEM, USER_TEMPLATE
from .providers import LLMClient, LLMError

log = logging.getLogger(__name__)


class _Skipped(Exception):
    """A batch deliberately not sent (circuit breaker open or time budget exhausted)."""


def _render_candidate(cid: str, c: Candidate, show: Show) -> tuple[str, dict[int, tuple[int, int]]]:
    line_map: dict[int, tuple[int, int]] = {}
    clip_lines = []
    n = 0
    for si, seg in enumerate(c.segments):
        ep = show.episode(seg.episode)
        if si > 0:
            clip_lines.append("   --- JUMP CUT ---")
        for b in ep.beats[seg.first_beat:seg.last_beat + 1]:
            n += 1
            line_map[n] = (si, b.idx)
            clip_lines.append(f"L{n} [Ep {ep.number} {fmt(b.start)}-{fmt(b.end)}] {b.display()}")
    first = c.segments[0]
    ep0 = show.episode(first.episode)
    ctx = [f"   [Ep {ep0.number} {fmt(b.start)}] {b.display()}" for b in ep0.beats[max(0, first.first_beat - 2):first.first_beat]]
    last = c.segments[-1]
    epl = show.episode(last.episode)
    after = [f"   [Ep {epl.number} {fmt(b.start)}] {b.display()}" for b in epl.beats[last.last_beat + 1:last.last_beat + 2]]
    logline = (ep0.meta.get("episode_logline") or ep0.meta.get("logline") or ep0.meta.get("synopsis") or "").strip()
    if logline:
        ctx.insert(0, f"   (Episode {ep0.number} logline, for your understanding only — not on screen: {logline[:300]})")
    text = CANDIDATE_TEMPLATE.format(cid=cid, kind=c.kind, duration=c.duration,
                                     episodes=", ".join(str(s.episode) for s in c.segments),
                                     context="\n".join(ctx) or "   (start of episode)", clip="\n".join(clip_lines),
                                     after="\n".join(after) or "   (end of episode)")
    return text, line_map


def _apply_edit(c: Candidate, res: dict, line_map: dict, show: Show, cfg: dict, lex) -> Optional[str]:
    """Let the model tighten a continuous clip — only to real beats, only inside the clip, only within length limits."""
    if c.kind != "continuous" or not cfg["llm"].get("allow_boundary_edits", True):
        return None
    try:
        sl, el = int(res.get("start_line")), int(res.get("end_line"))
    except (TypeError, ValueError):
        return None
    if sl not in line_map or el not in line_map or sl > el:
        return "rejected: line numbers outside the clip"
    _, i = line_map[sl]
    _, j = line_map[el]
    seg = c.segments[0]
    if (i, j) == (seg.first_beat, seg.last_beat):
        return None
    ep = show.episode(seg.episode)
    while i <= j and ep.beats[i].kind == "scene":
        i += 1
    dur = ep.span_end(i, j) - ep.beats[i].start
    lo, hi = float(cfg["promo"]["min_seconds"]), float(cfg["promo"]["max_seconds"])
    if not (lo <= dur <= hi):
        return f"rejected: edited length {dur:.1f}s outside {lo:.0f}-{hi:.0f}s"
    c.segments = [Segment(ep.number, ep.beats[i].start, ep.span_end(i, j), i, j)]
    keep = {k: c.features.get(k) for k in ("llm",)}
    c.features = window_features(show, ep, i, j, cfg, lex)
    c.features.update({k: v for k, v in keep.items() if v is not None})
    return f"tightened to L{sl}-L{el} ({dur:.1f}s)"


def llm_rerank(cands: list[Candidate], show: Show, cfg: dict, client: LLMClient, lex, scorer) -> dict:
    lc = cfg["llm"]
    top_n = int(lc.get("rerank_top_n", 30))
    bs = max(1, int(lc.get("batch_size", 5)))
    alpha = float(lc.get("blend_alpha", 0.5))
    ordered = sorted(cands, key=lambda c: -c.score)
    targets = ordered[:top_n]
    chars = ", ".join(list(show.characters)[:8]) or "unknown"
    batches = [targets[k:k + bs] for k in range(0, len(targets), bs)]
    report = {"judged": 0, "failed_batches": 0, "skipped_batches": 0, "edits": 0, "rejected_edits": 0, "errors": []}
    import os
    import threading
    import time as _time
    budget = float(lc.get("max_total_seconds", 45 if (os.environ.get("VERCEL") or os.environ.get("PROMO_READONLY_FS")) else 300))
    deadline = _time.monotonic() + budget
    state = {"consecutive_fail": 0, "open": False}
    lock = threading.Lock()

    def run_batch(batch: list[Candidate]):
        # circuit breaker + time budget: stop calling a dead or slow provider, keep the rules ranking
        if state["open"]:
            raise _Skipped("circuit open after repeated LLM failures")
        if _time.monotonic() > deadline:
            raise _Skipped(f"LLM time budget of {budget:.0f}s used up")
        blocks, maps = [], {}
        for n, c in enumerate(batch):
            cid = f"c{n + 1}"
            text, lm = _render_candidate(cid, c, show)
            blocks.append(text)
            maps[cid] = (c, lm)
        user = USER_TEMPLATE.format(show_title=show.title, characters=chars, min_s=cfg["promo"]["min_seconds"],
                                    max_s=cfg["promo"]["max_seconds"], candidates="\n".join(blocks))
        try:
            out = client.complete_json(SYSTEM, user)
        except Exception:
            with lock:
                state["consecutive_fail"] += 1
                if state["consecutive_fail"] >= int(lc.get("circuit_breaker_failures", 2)):
                    state["open"] = True
            raise
        with lock:
            state["consecutive_fail"] = 0
        return out, maps

    with ThreadPoolExecutor(max_workers=max(1, int(lc.get("max_concurrency", 3)))) as pool:
        futures = [pool.submit(run_batch, b) for b in batches]
        for fut in futures:
            try:
                data, maps = fut.result()
            except _Skipped as exc:
                report["skipped_batches"] += 1
                if str(exc) not in report["errors"]:
                    report["errors"].append(str(exc))
                continue
            except (LLMError, Exception) as exc:  # noqa: BLE001 - keep heuristic ranking on any failure
                report["failed_batches"] += 1
                report["errors"].append(str(exc)[:200])
                log.warning("LLM batch failed: %s", exc)
                continue
            for res in data.get("results", []) if isinstance(data, dict) else []:
                cid = str(res.get("id", ""))
                if cid not in maps:
                    continue
                c, lm = maps[cid]
                try:
                    overall = max(0.0, min(10.0, float(res.get("overall", 0))))
                except (TypeError, ValueError):
                    continue
                c.features["llm"] = {
                    "overall": overall,
                    "hook_score": res.get("hook_score"), "cliffhanger_score": res.get("cliffhanger_score"),
                    "standalone_score": res.get("standalone_score"),
                    "hook": str(res.get("hook", ""))[:160], "cliffhanger": str(res.get("cliffhanger", ""))[:160],
                    "why": str(res.get("why", ""))[:240], "red_flags": [str(x)[:80] for x in (res.get("red_flags") or [])][:5],
                }
                edit = _apply_edit(c, res, lm, show, cfg, lex)
                if edit:
                    c.features["llm"]["edit"] = edit
                    report["rejected_edits" if edit.startswith("rejected") else "edits"] += 1
                heur = scorer(c)
                c.features["heuristic_score"] = heur
                c.features["llm_score"] = overall * 10
                c.score = round(alpha * heur + (1 - alpha) * overall * 10, 2)
                report["judged"] += 1
    report["circuit_breaker_open"] = state["open"]
    report["stats"] = dict(client.stats)
    if hasattr(client, "switches"):
        report["provider_switches"] = list(client.switches)
    report["model"] = client.model
    report["provider"] = client.settings.provider
    return report
