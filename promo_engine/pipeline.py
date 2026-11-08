"""End-to-end orchestration.

    inputs ─► load ─► parse ─► characters ─► beat signals ─► candidate windows ─► refine
          ─► montages ─► (LLM re-rank, optional) ─► diversity selection ─► promos
          ─► posting plan ─► quality flags ─► (manual comparison) ─► metrics ─► exports
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from . import __version__
from .analysis.characters import build_registry
from .analysis.features import annotate_show, intensity_curve
from .analysis.lexicon import Lexicon
from .config import apply_platform, load_config
from .evaluate.compare import compare
from .evaluate.manual import ManualPromo, load_manual
from .evaluate.metrics import run_metrics
from .evaluate.quality import flag_promo, quality_report
from .generate.boundaries import refine, variants
from .generate.candidates import Candidate, generate_candidates
from .generate.montage import generate_montages
from .ingest.loader import load_inputs
from .ingest.parser import ScreenplayParser
from .llm import build_client
from .llm.judge import llm_rerank
from .models import Promo, Show
from .rank.diversity import select_diverse
from .rank.explain import cliff_info, hook_info, why_line
from .rank.schedule import schedule
from .rank.scorer import make_scorer

Progress = Optional[Callable[[str, float], None]]
log = logging.getLogger(__name__)


@dataclass
class RunResult:
    run_id: str
    show: Show
    promos: list[Promo]
    pool: list[Candidate]
    cfg: dict
    timings: dict[str, float]
    warnings: list[str]
    heatmap: list[dict]
    quality: dict
    metrics: dict
    comparison: Optional[dict] = None
    manual: list[ManualPromo] = field(default_factory=list)
    llm: dict = field(default_factory=dict)
    lexicon: Optional[Lexicon] = None
    scorer: Any = None

    def to_dict(self, include_beats: bool = False) -> dict:
        eps = []
        for e in self.show.episodes:
            d = {"number": e.number, "title": e.title, "source": e.source, "duration": round(e.duration, 2),
                 "beats": len(e.beats), "scenes": len(e.scenes), "parse_confidence": e.parse_confidence,
                 "warnings": [w for w in e.warnings if not w.startswith("offset=")]}
            if include_beats:
                d["timeline"] = [{"idx": b.idx, "start": b.start, "end": b.end, "kind": b.kind, "speaker": b.speaker,
                                  "text": b.text, "timed": b.timed, "hook": b.signals.get("hook"), "cliff": b.signals.get("cliff"),
                                  "intensity": b.signals.get("intensity")} for b in e.beats]
            eps.append(d)
        pc = self.cfg["promo"]
        return {
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "version": __version__,
            "show": {"title": self.show.title, "episodes": eps, "characters": self.show.characters,
                     "total_minutes": round(self.show.total_seconds / 60, 2)},
            "settings": {"platform": self.cfg.get("_platform", "any"), "min_seconds": pc["min_seconds"],
                         "max_seconds": pc["max_seconds"], "target_seconds": pc["target_seconds"], "top_k": pc["top_k"],
                         "weights": self.cfg["weights"], "weights_source": self.cfg.get("_weights_source"),
                         "llm": self.llm.get("settings", {"enabled": False})},
            "promos": [p.to_dict() for p in sorted(self.promos, key=lambda p: p.rank)],
            "posting_plan": [{"post_order": p.post_order, "id": p.id, "rank": p.rank, "rationale": p.post_rationale}
                             for p in sorted(self.promos, key=lambda p: p.post_order)],
            "heatmap": self.heatmap,
            "quality": self.quality,
            "metrics": self.metrics,
            "comparison": self.comparison,
            "manual": [m.to_dict() for m in self.manual],
            "llm_report": {k: v for k, v in self.llm.items() if k != "settings"},
            "pool": [{"episode": c.segments[0].episode, "start": round(c.segments[0].start, 2), "end": round(c.segments[-1].end, 2),
                      "segments": len(c.segments), "score": c.score} for c in sorted(self.pool, key=lambda c: -c.score)[:300]],
            "warnings": self.warnings,
        }


def _transcript(c: Candidate, show: Show, hook_beat: Optional[int], cliff_beat: Optional[int]) -> list[dict]:
    rows = []
    for si, seg in enumerate(c.segments):
        ep = show.episode(seg.episode)
        for b in ep.beats[seg.first_beat:seg.last_beat + 1]:
            rows.append({"segment": si + 1, "episode": ep.number, "start": round(b.start, 2), "end": round(b.end, 2),
                         "kind": b.kind, "speaker": b.speaker, "text": b.text, "manner": b.manner, "timed": b.timed,
                         "is_hook": si == 0 and b.idx == hook_beat,
                         "is_cliff": si == len(c.segments) - 1 and b.idx == cliff_beat,
                         "intensity": b.signals.get("intensity", 0.0)})
    return rows


def build_promo(c: Candidate, pid: str, show: Show, cfg: dict) -> Promo:
    hook = hook_info(c, show)
    cliff = cliff_info(c, show)
    why = why_line(c, hook, cliff)
    llm = c.features.get("llm")
    if llm:
        hook["llm"] = llm.get("hook")
        cliff["llm"] = llm.get("cliffhanger")
        if llm.get("why"):
            why = llm["why"]
    p = Promo(id=pid, segments=list(c.segments), kind=c.kind, score=c.score,
              heuristic_score=c.features.get("heuristic_score", c.score),
              llm_score=c.features.get("llm_score"), breakdown=dict(c.breakdown), hook=hook, cliffhanger=cliff,
              why=why, tropes=list(c.features.get("tropes") or []), source="rules+llm" if llm else "rules",
              llm_notes=llm or {})
    p.transcript = _transcript(c, show, c.features.get("hook_beat"), c.features.get("cliff_beat"))
    p.characters = sorted({r["speaker"] for r in p.transcript if r["speaker"]})
    p.variants = variants(c, show, cfg)
    p.flags = flag_promo(p, c.features, cfg)
    p.llm_notes = {**(llm or {}), "standalone_reasons": c.features.get("standalone_reasons", []),
                   "refined": c.features.get("refined")}
    return p


def _title_from_inputs(inputs) -> Optional[str]:
    """'data/input/the_maid_show.zip' -> 'The Maid Show' (used only when no title is given)."""
    import os
    import re
    first = inputs[0] if isinstance(inputs, list) and inputs else inputs
    name = first[0] if isinstance(first, tuple) else str(first)
    from pathlib import Path as _P

    from .ingest.loader import _ext, _is_junk
    pth = _P(name)
    if not isinstance(first, tuple) and pth.is_dir():
        kids = [k for k in pth.iterdir() if not _is_junk(k.name)]
        if len(kids) == 1 and (kids[0].is_dir() or kids[0].suffix.lower() == ".zip"):
            name = str(kids[0])          # data/input/<Show name>/ -> use the show folder's name
    base = os.path.basename(os.path.normpath(name))
    stem = base[: -len(_ext(base))] if _ext(base) else base
    if isinstance(first, tuple) and "/" in name:
        stem = name.split("/")[0]
    stem = re.sub(r"[_]+|(?<=\w)[-.](?=\w)|\s+-\s+", " ", stem).strip(" .-_")
    if not stem or stem.lower() in ("input", "inputs", "data", "screenplays", "show", "episodes", "upload"):
        return None
    if re.fullmatch(r"(ep(isode)?\s*)?\d+", stem, re.I):
        return None
    from .ingest.loader import episode_from_name
    if episode_from_name(stem) is not None or re.search(r"\b(ep|episode)\b", stem, re.I):
        return None          # "episode 001 Episode 1671703" is an episode file, not the show
    return stem if (stem != stem.lower() and stem != stem.upper()) else stem.title()


def run_pipeline(inputs, *, cfg: Optional[dict] = None, config_path: Optional[str] = None, platform: Optional[str] = None,
                 top_k: Optional[int] = None, manual=None, use_llm: Optional[bool] = None, llm_key: Optional[str] = None,
                 llm_provider: Optional[str] = None, llm_model: Optional[str] = None, show_title: Optional[str] = None,
                 progress: Progress = None, overrides: Optional[dict] = None) -> RunResult:
    def tick(stage: str, frac: float):
        if progress:
            progress(stage, frac)

    degraded: list[str] = []
    warnings: list[str] = []

    def guard(stage: str, fn, fallback):
        """Run one stage; on any error keep going with a safe fallback and say so in the report."""
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - one broken stage must not cost the editor the whole run
            log.exception("stage %s failed", stage)
            degraded.append(stage)
            warnings.append(f"Stage '{stage}' failed ({type(exc).__name__}: {exc}); continued with a fallback.")
            return fallback() if callable(fallback) else fallback

    try:
        cfg = cfg or load_config(config_path, overrides)
        cfg = apply_platform(cfg, platform)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        from .config import deep_merge
        from .defaults import DEFAULT_CONFIG
        warnings.append(f"Config could not be loaded ({exc}); using built-in defaults.")
        cfg = apply_platform(deep_merge(DEFAULT_CONFIG, overrides or {}), platform)
        cfg.setdefault("_weights_source", "default")
    if top_k:
        cfg["promo"]["top_k"] = max(1, int(top_k))
    timings: dict[str, float] = {}
    t = time.perf_counter()

    tick("Reading files", 0.05)
    docs = load_inputs(inputs, warnings) if not (isinstance(inputs, list) and inputs and hasattr(inputs[0], "text")) else inputs
    if not docs:
        raise ValueError("No readable screenplay files found. Supported: .txt .md .pdf .docx .odt .html .srt .vtt .csv .tsv "
                         ".xlsx .json .fountain and .zip" + (f" — problems: {'; '.join(warnings[:3])}" if warnings else ""))
    timings["ingest"] = time.perf_counter() - t

    tick("Parsing screenplays", 0.15)
    t = time.perf_counter()
    lex = Lexicon()
    from .analysis.lexicon import BAD_PATTERNS
    from .config import load_warnings
    warnings += load_warnings() + [f"Lexicon pattern skipped: {b}" for b in dict.fromkeys(BAD_PATTERNS)]
    if not show_title and cfg.get("show_title", "Untitled show") == "Untitled show":
        show_title = _title_from_inputs(inputs)
    show = ScreenplayParser(cfg, lex.raw).parse_docs(docs, title=show_title or cfg.get("show_title") or "Untitled show")
    show.episodes = [e for e in show.episodes if any(b.kind != "scene" for b in e.beats)]
    if not show.episodes:
        raise ValueError("Files were read but no screenplay lines were recognised. Run `promo-finder parse -v 10` to see what was read."
                         + (f" Warnings: {'; '.join(show.warnings[:3])}" if show.warnings else ""))
    warnings += show.warnings
    guard("characters", lambda: build_registry(show), {})
    timings["parse"] = time.perf_counter() - t

    tick("Scoring every beat", 0.3)
    t = time.perf_counter()
    guard("signals", lambda: annotate_show(show, lex), None)
    timings["signals"] = time.perf_counter() - t

    tick("Generating candidate windows", 0.4)
    t = time.perf_counter()
    scorer = make_scorer(cfg)
    pool = generate_candidates(show, cfg, lex, scorer, warnings)
    pool.sort(key=lambda c: -c.score)

    def _refine_all():
        out = []
        for c in pool[:300]:
            try:
                out.append(refine(c, show, cfg, lex, scorer))
            except Exception:  # noqa: BLE001
                out.append(c)
        return out + pool[300:]
    pool = guard("refine", _refine_all, lambda: pool)
    timings["candidates"] = time.perf_counter() - t

    tick("Building multi-segment promos", 0.5)
    t = time.perf_counter()
    montages = guard("montages", lambda: generate_montages(show, cfg, lex, scorer, pool), [])
    pool = pool + montages
    timings["montages"] = time.perf_counter() - t
    if not pool:
        raise ValueError("No candidate clips could be built (episodes may be shorter than the minimum promo length "
                         f"of {cfg['promo']['min_seconds']}s, or have no timed lines).")

    llm_info: dict = {}
    client = None
    want_llm = use_llm if use_llm is not None else True
    if want_llm:
        client = guard("llm_setup", lambda: build_client(cfg, key=llm_key, provider=llm_provider, model=llm_model), None)
    if client is not None:
        tick(f"LLM judging top candidates ({client.settings.provider})", 0.6)
        t = time.perf_counter()
        snapshot = [(c, list(c.segments), dict(c.features), c.score, dict(c.breakdown)) for c in pool]
        try:
            llm_info = llm_rerank(pool, show, cfg, client, lex, scorer)
        except Exception as exc:  # noqa: BLE001
            for c, segs, feats, score, bd in snapshot:      # roll back any half-applied re-ranking
                c.segments, c.features, c.score, c.breakdown = segs, feats, score, bd
            llm_info = {"error": str(exc)[:300]}
            warnings.append(f"LLM step skipped, rules ranking kept: {exc}")
        if llm_info.get("failed_batches") or llm_info.get("skipped_batches"):
            warnings.append(f"LLM judged {llm_info.get('judged', 0)} candidates; {llm_info.get('failed_batches', 0)} batch(es) failed and "
                            f"{llm_info.get('skipped_batches', 0)} were skipped — those stay rules-ranked.")
        try:
            llm_info["settings"] = client.settings.describe() | {"model": client._model or client.spec.default_model}
        except Exception:  # noqa: BLE001
            llm_info["settings"] = {"enabled": True}
        timings["llm"] = time.perf_counter() - t
    else:
        from .llm.base import resolve_settings
        llm_info = {"settings": resolve_settings(key=llm_key).describe() | {"enabled": False, "reason": "no key or disabled"}}

    tick("Selecting a diverse top list", 0.8)
    t = time.perf_counter()
    chosen = guard("select", lambda: select_diverse(pool, cfg), lambda: sorted(pool, key=lambda c: -c.score)[: int(cfg["promo"]["top_k"])])
    if not chosen:
        # every candidate fell below min_score: still give the editor the best available, clearly flagged
        relaxed = dict(cfg)
        relaxed["promo"] = dict(cfg["promo"], min_score=0)
        chosen = guard("select_relaxed", lambda: select_diverse(pool, relaxed), lambda: sorted(pool, key=lambda c: -c.score)[: int(cfg["promo"]["top_k"])])
        for c in chosen:
            c.features["below_min_score"] = True
        warnings.append(f"No candidate reached the minimum score ({cfg['promo'].get('min_score')}); showing the best available, flagged.")
    chosen.sort(key=lambda c: -c.score)
    promos: list[Promo] = []
    for c in chosen:
        try:
            promos.append(build_promo(c, f"P{len(promos) + 1:02d}", show, cfg))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"One promo could not be described and was dropped: {exc}")
    for k, p in enumerate(promos, 1):
        p.rank = k
        p.post_order = k
        if "below_min_score" in (chosen[k - 1].features if k - 1 < len(chosen) else {}):
            p.flags.append("below_min_score")
    guard("schedule", lambda: schedule(promos, show, cfg), None)
    timings["rank"] = time.perf_counter() - t

    manual_promos: list[ManualPromo] = []
    comparison = None
    if manual is not None:
        tick("Comparing with your manual promos", 0.9)
        t = time.perf_counter()
        manual_promos = guard("manual_load", lambda: manual if isinstance(manual, list) else load_manual(manual, warnings), [])
        if manual_promos:
            comparison = guard("compare", lambda: compare(promos, manual_promos, show, cfg, lex, scorer, pool), None)
        elif manual is not None:
            warnings.append("Manual promos file was given but no promos could be read from it (see template).")
        timings["compare"] = time.perf_counter() - t

    quality = guard("quality", lambda: quality_report(promos, show),
                    {"flag_counts": {}, "clean_promos": 0, "clean_share": 0, "review_first": [], "parse_issues": [], "known_failure_modes": []})
    metrics = guard("metrics", lambda: run_metrics(show, promos, len(pool), timings, llm_info if client else None, cfg), {})
    if comparison and isinstance(metrics, dict):
        metrics["agreement_with_manual"] = comparison["summary"]
    if isinstance(metrics, dict):
        metrics["degraded_stages"] = degraded
    heatmap = guard("heatmap", lambda: intensity_curve(show), [])
    tick("Done", 1.0)
    return RunResult(run_id=uuid.uuid4().hex[:10], show=show, promos=promos, pool=pool, cfg=cfg, timings=timings,
                     warnings=list(dict.fromkeys(warnings)), heatmap=heatmap, quality=quality, metrics=metrics,
                     comparison=comparison, manual=manual_promos, llm=llm_info, lexicon=lex, scorer=scorer)
