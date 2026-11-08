"""Command-line interface.

    promo-finder run   --input data/input [--manual data/manual_promos/my_manual_promos.csv] [--out outputs/run1]
    promo-finder parse --input data/input            # inspect how the screenplays were understood
    promo-finder learn --input data/input --manual …  # fit scoring weights to your manual picks
    promo-finder llm-check [--key …]                  # which provider/model a key maps to + a test call
    promo-finder serve [--port 8000]                  # web app (API + built frontend)

(or `python -m promo_engine …`)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .config import LEARNED_WEIGHTS, ROOT, load_config
from .timecode import fmt


def _load_env():
    """Tiny .env loader (no extra dependency)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _progress(stage: str, frac: float):
    bar = "█" * int(frac * 20)
    print(f"\r  [{bar:<20}] {stage:<45}", end="" if frac < 1 else "\n", file=sys.stderr, flush=True)


def cmd_run(a) -> int:
    from .export.exporters import save_outputs
    from .pipeline import run_pipeline
    res = run_pipeline(a.input, config_path=a.config, platform=a.platform, top_k=a.top_k, manual=a.manual,
                       use_llm=not a.no_llm, llm_key=a.llm_key, llm_model=a.llm_model, show_title=a.title,
                       progress=None if a.quiet else _progress)
    run = res.to_dict(include_beats=a.with_timeline)
    out = Path(a.out or ROOT / "outputs" / f"run_{datetime.now():%Y%m%d_%H%M%S}")
    files = save_outputs(run, out, res.cfg)
    m = run["metrics"]
    print(f"\n{run['show']['title']}: {m['input']['episodes']} episodes, {m['input']['beats']} beats "
          f"({m['input']['timestamp_coverage']:.0%} timestamped) -> {len(run['promos'])} promos in {m['operations']['runtime_s']:.2f}s")
    llm = run["settings"]["llm"]
    print(f"Ranking: {'rules + ' + str(llm.get('provider')) + ' / ' + str(llm.get('model')) if llm.get('enabled') else 'rules only (set LLM_API_KEY to add an LLM judge)'}")
    print()
    for p in run["promos"][: a.show]:
        segs = " + ".join(f"Ep{s['episode']} {fmt(s['start'])}-{fmt(s['end'])}" for s in p["segments"])
        print(f"#{p['rank']:>2} [{p['score']:5.1f}] {segs:<38} {p['duration']:5.1f}s  post #{p['post_order']}")
        print(f"     HOOK  {p['hook'].get('type')}: {p['hook'].get('text', '')[:90]}")
        print(f"     CLIFF {p['cliffhanger'].get('type')}: {p['cliffhanger'].get('text', '')[:90]}")
        print(f"     WHY   {p['why'][:120]}")
    if run.get("comparison"):
        s = run["comparison"]["summary"]
        print(f"\n>>> {s['headline']}  recall={s['recall']:.0%}  recall@10={s['recall_at_k'].get('10')}  mean IoU={s['mean_iou_matched']}")
    for w in run["warnings"][:10]:
        print(f"  ! {w}", file=sys.stderr)
    print(f"\nOutputs written to {out}:")
    for name in files:
        print(f"  - {name}")
    return 0


def cmd_parse(a) -> int:
    from .analysis.characters import build_registry
    from .ingest import load_inputs
    from .ingest.parser import ScreenplayParser
    warnings: list[str] = []
    docs = load_inputs(a.input, warnings)
    show = ScreenplayParser(load_config(a.config)).parse_docs(docs)
    build_registry(show)
    print(f"{len(docs)} file(s) -> {len(show.episodes)} episode(s)")
    for e in show.episodes:
        print(f"  Ep {e.number:>3}  {e.duration:7.1f}s  {len(e.beats):4d} beats  {len(e.scenes):3d} scenes  "
              f"timestamps {e.parse_confidence:.0%}  ({e.source})")
        if a.verbose:
            for b in e.beats[: a.verbose]:
                print(f"         {fmt(b.start)}-{fmt(b.end)} {'*' if not b.timed else ' '} {b.kind:<8} {b.display()[:90]}")
    print("Characters:", ", ".join(f"{k} ({v['lines']})" for k, v in list(show.characters.items())[:12]))
    for w in warnings + show.warnings:
        print("  !", w)
    if a.json:
        Path(a.json).write_text(json.dumps([{"episode": e.number, "beats": [b.__dict__ | {"signals": {}} for b in e.beats]}
                                            for e in show.episodes], indent=1, default=str), encoding="utf-8")
        print("timeline written to", a.json)
    return 0


def cmd_learn(a) -> int:
    from .evaluate.compare import overlap_stats
    from .generate.candidates import score_manual_window
    from .pipeline import run_pipeline
    from .rank.learner import build_samples, evaluate, fit_logistic, save_learned, to_weights
    cfg = load_config(a.config, {"use_learned_weights": False})
    cfg["use_learned_weights"] = False
    res = run_pipeline(a.input, cfg=cfg, manual=a.manual, use_llm=False)
    if not res.manual:
        print("No manual promos loaded — nothing to learn from.")
        return 1
    from .models import Promo

    def is_pos(c):
        tmp = Promo(id="x", segments=c.segments)
        return any(overlap_stats(m, tmp)["iou"] >= 0.3 for m in res.manual)

    extra = []
    for m in res.manual:
        if len(m.segments) == 1:
            ep, s, e = m.segments[0]
            c = score_manual_window(res.show, ep, s, e, res.cfg, res.lexicon, res.scorer)
            if c:
                extra.append(c.features)
    # editor keep/reject clicks from the web app become extra labelled windows
    fb = ROOT / "data" / "feedback" / "feedback.jsonl"
    fb_pos, fb_neg = 0, []
    if fb.exists():
        for line in fb.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("episode") is None or item.get("start") is None or item.get("end") is None:
                continue
            c = score_manual_window(res.show, int(item["episode"]), float(item["start"]), float(item["end"]),
                                    res.cfg, res.lexicon, res.scorer)
            if c is None:
                continue
            if item.get("verdict") == "accept":
                extra.append(c.features)
                fb_pos += 1
            elif item.get("verdict") == "reject":
                fb_neg.append((c.features, 0))
    samples = build_samples(res.pool, extra, is_pos) + fb_neg
    w, b = fit_logistic(samples)
    stats = evaluate(samples, w, b)
    weights = to_weights(w, res.cfg["weights"])
    print("Training:", stats, f"| editor feedback used: {fb_pos} keep, {len(fb_neg)} reject")
    for k, v in weights.items():
        print(f"  {k:<16} {res.cfg['weights'].get(k, 0):.3f} -> {v:.3f}")
    if a.dry_run:
        return 0
    save_learned(weights, LEARNED_WEIGHTS, stats)
    print(f"Saved {LEARNED_WEIGHTS}. Next runs use these weights (set use_learned_weights: false to disable).")
    return 0


def cmd_llm_check(a) -> int:
    from .llm import build_client, resolve_settings
    s = resolve_settings(key=a.key)
    print("Detected:", json.dumps(s.describe(), indent=2))
    if not s.enabled:
        from .llm.base import unknown_key_hint
        print(unknown_key_hint(s.key))
        return 1
    client = build_client(load_config(), key=a.key)
    try:
        print("Model:", client.model)
        print("Ping:", client.ping())
        route = getattr(client, "stats", {}).get("gemini_route")
        if route:
            print("Google endpoint used:", route)
    except Exception as exc:  # noqa: BLE001
        print("Call failed:", exc)
        msg = str(exc)
        if "network error" in msg:
            print("Could not reach the provider (no internet, a firewall/VPN or a proxy blocked it). "
                  "This is a connection problem, not a key problem. Try again on a normal network.")
        elif "401" in msg or "403" in msg:
            print("The provider rejected the key. Check it is copied completely, that the Gemini API is enabled for its "
                  "project, and (for a new key) wait a minute. You can also try LLM_MODEL=gemini-2.5-flash.")
        elif "404" in msg:
            print("The model was not found. Set LLM_MODEL to a model your key can use (e.g. gemini-2.5-flash).")
        return 2
    return 0


def cmd_serve(a) -> int:
    import uvicorn
    uvicorn.run("backend.app:app", host=a.host, port=a.port, reload=a.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="promo-finder", description="Find ready-to-cut promos in microdrama screenplays.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="find, rank and export promos")
    r.add_argument("--input", "-i", required=True, help="file, folder or .zip of screenplays")
    r.add_argument("--manual", "-m", help="your manual promos (csv/json/xlsx/txt) to compare against")
    r.add_argument("--out", "-o", help="output folder (default outputs/run_<timestamp>)")
    r.add_argument("--platform", choices=["any", "tiktok", "reels", "shorts"], default="any")
    r.add_argument("--top-k", type=int)
    r.add_argument("--config", help="YAML overriding config/default.yaml")
    r.add_argument("--title", help="show title for reports")
    r.add_argument("--no-llm", action="store_true", help="rules only, even if a key is set")
    r.add_argument("--llm-key", help="override LLM_API_KEY for this run")
    r.add_argument("--llm-model", help="force a model id")
    r.add_argument("--with-timeline", action="store_true", help="include every parsed beat in promos.json")
    r.add_argument("--show", type=int, default=10, help="promos to print")
    r.add_argument("--quiet", action="store_true")
    r.set_defaults(fn=cmd_run)
    pa = sub.add_parser("parse", help="show how the screenplays were parsed")
    pa.add_argument("--input", "-i", required=True)
    pa.add_argument("--config")
    pa.add_argument("--verbose", "-v", type=int, default=0, help="print first N beats per episode")
    pa.add_argument("--json", help="write the full timeline to this JSON file")
    pa.set_defaults(fn=cmd_parse)
    le = sub.add_parser("learn", help="fit scoring weights to your manual promos")
    le.add_argument("--input", "-i", required=True)
    le.add_argument("--manual", "-m", required=True)
    le.add_argument("--config")
    le.add_argument("--dry-run", action="store_true")
    le.set_defaults(fn=cmd_learn)
    lc = sub.add_parser("llm-check", help="detect provider from a key and make a test call")
    lc.add_argument("--key")
    lc.set_defaults(fn=cmd_llm_check)
    sv = sub.add_parser("serve", help="run the web app")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--reload", action="store_true")
    sv.set_defaults(fn=cmd_serve)
    return p


def main(argv=None) -> int:
    _load_env()
    sys.path.insert(0, str(ROOT))
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
