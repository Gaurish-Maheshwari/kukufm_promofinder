"""JSON / CSV / Markdown exports + `save_outputs` that writes the whole raw-outputs folder.

All exporters take the run *dict* (RunResult.to_dict()), so the web API can
produce any export statelessly from a result the browser already holds.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from ..timecode import fmt, smpte


def to_json(run: dict) -> str:
    return json.dumps(run, indent=2, ensure_ascii=False, default=list)


def _seg_rows(run: dict):
    for p in run["promos"]:
        for k, s in enumerate(p["segments"], 1):
            yield p, k, s


def promos_csv(run: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "post_order", "promo_id", "score", "kind", "segment", "episode", "start", "end", "start_s", "end_s",
                "segment_s", "promo_s", "hook_type", "hook", "hook_at_s", "cliffhanger_type", "cliffhanger", "why",
                "tropes", "flags", "source"])
    for p, k, s in _seg_rows(run):
        w.writerow([p["rank"], p["post_order"], p["id"], p["score"], p["kind"], k, s["episode"], fmt(s["start"]), fmt(s["end"]),
                    round(s["start"], 2), round(s["end"], 2), round(s["end"] - s["start"], 2), p["duration"],
                    p["hook"].get("type"), p["hook"].get("text"), p["hook"].get("at"), p["cliffhanger"].get("type"),
                    p["cliffhanger"].get("text"), p["why"], ";".join(p["tropes"]), ";".join(p["flags"]), p["source"]])
    return buf.getvalue()


def cut_sheet_csv(run: dict, pre_roll: float = 0.0, post_roll: float = 0.4, fps: int = 30) -> str:
    """What an editor actually needs: source episode, IN/OUT in SMPTE and seconds, with handles."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["post_order", "rank", "promo_id", "segment", "episode", "source_file", "in_tc", "out_tc", "in_s", "out_s",
                "duration_s", "handles", "hook", "cliffhanger", "notes"])
    sources = {e["number"]: e["source"] for e in run["show"]["episodes"]}
    durations = {e["number"]: e["duration"] for e in run["show"]["episodes"]}
    for p in sorted(run["promos"], key=lambda x: x["post_order"]):
        for k, s in enumerate(p["segments"], 1):
            a = max(0.0, s["start"] - pre_roll)
            b = min(durations.get(s["episode"], s["end"] + post_roll), s["end"] + post_roll)
            w.writerow([p["post_order"], p["rank"], p["id"], k, s["episode"], sources.get(s["episode"], ""),
                        smpte(a, fps), smpte(b, fps), round(a, 3), round(b, 3), round(b - a, 2),
                        f"pre {pre_roll:.1f}s / post {post_roll:.1f}s", p["hook"].get("text", "") if k == 1 else "",
                        p["cliffhanger"].get("text", "") if k == len(p["segments"]) else "", "; ".join(p["flags"])])
    return buf.getvalue()


def comparison_csv(run: dict) -> str:
    cmp = run.get("comparison")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["manual_id", "manual_segments", "manual_duration_s", "status", "ai_id", "ai_rank", "ai_segments",
                "iou", "coverage", "start_delta_s", "end_delta_s", "hook_agrees", "diagnosis"])
    if not cmp:
        return buf.getvalue()

    def segtxt(segs):
        return " + ".join(f"Ep{s['episode']} {fmt(s['start'])}-{fmt(s['end'])}" for s in segs)

    for r in cmp["rows"]:
        ai = r.get("ai") or {}
        w.writerow([r["manual"]["id"], segtxt(r["manual"]["segments"]), r["manual"]["duration"], r["status"],
                    ai.get("id", ""), ai.get("rank", ""), segtxt(ai.get("segments", [])), r["iou"], r["coverage"],
                    r["start_delta"], r["end_delta"], r["hook_agrees"], r["diagnosis"]])
    return buf.getvalue()


def _segs_md(segs) -> str:
    return " + ".join(f"Ep {s['episode']} `{fmt(s['start'])} → {fmt(s['end'])}`" for s in segs)


def markdown_report(run: dict) -> str:
    m = run["metrics"]
    L: list[str] = []
    L.append(f"# Promo report — {run['show']['title']}")
    L.append("")
    st = run["settings"]
    llm = st.get("llm", {})
    L.append(f"Run `{run['run_id']}` · {run['created_at']} · v{run['version']} · platform **{st['platform']}** "
             f"({st['min_seconds']}–{st['max_seconds']} s) · ranking: **{'rules + ' + str(llm.get('provider')) + ' (' + str(llm.get('model')) + ')' if llm.get('enabled') else 'rules only'}**")
    L.append("")
    L.append(f"**Input:** {m['input']['episodes']} episodes · {m['input']['beats']} lines/actions · "
             f"{m['input']['show_minutes']} min · {m['input']['timestamp_coverage']:.0%} of lines carried explicit timestamps.")
    bc = m["brief_compliance"]
    L.append(f"**Output:** {m['output']['promos']} promos ({m['output']['montages']} multi-segment) from "
             f"{m['output']['candidates_scored']} scored candidates · {bc['duration_in_range']:.0%} within length · "
             f"{bc['hook_within_3s']:.0%} hook ≤3 s · {bc['strong_cliffhanger']:.0%} strong cliffhanger.")
    if run.get("comparison"):
        L.append("")
        L.append(f"**vs. your manual picks:** {run['comparison']['summary']['headline']}")
    L.append("")
    L.append("## Ranked promos")
    L.append("")
    L.append("| Rank | Post | ID | Score | Segments | Len | Hook | Cliffhanger |")
    L.append("|---:|---:|---|---:|---|---:|---|---|")
    for p in run["promos"]:
        L.append(f"| {p['rank']} | {p['post_order']} | {p['id']} | {p['score']:.0f} | {_segs_md(p['segments'])} | {p['duration']:.0f}s | "
                 f"{p['hook'].get('type', '')} | {p['cliffhanger'].get('type', '')} |")
    L.append("")
    L.append("## Posting plan — what to post first and why")
    L.append("")
    for row in run["posting_plan"]:
        L.append(f"{row['post_order']}. **{row['id']}** (rank {row['rank']}) — {row['rationale']}")
    L.append("")
    L.append("## Promo details")
    for p in run["promos"]:
        L.append("")
        L.append(f"### {p['rank']}. {p['id']} — score {p['score']:.0f} · {p['kind'].replace('_', ' ')} · {p['duration']:.1f}s")
        L.append("")
        for k, s in enumerate(p["segments"], 1):
            L.append(f"- Segment {k}: Episode {s['episode']}, **{fmt(s['start'])} → {fmt(s['end'])}** ({s['end'] - s['start']:.1f}s)")
        L.append(f"- **Hook** ({p['hook'].get('type')}, at {p['hook'].get('at', 0):.1f}s): {p['hook'].get('text')}")
        if p["hook"].get("llm"):
            L.append(f"  - LLM: {p['hook']['llm']}")
        L.append(f"- **Cliffhanger** ({p['cliffhanger'].get('type')}): {p['cliffhanger'].get('text')}")
        if p["cliffhanger"].get("llm"):
            L.append(f"  - LLM: {p['cliffhanger']['llm']}")
        L.append(f"- **Why it works:** {p['why']}")
        if p["tropes"]:
            L.append(f"- Tropes: {', '.join(p['tropes'])}")
        if p["flags"]:
            L.append(f"- ⚠ Flags: {', '.join(p['flags'])}")
        v = p.get("variants", {})
        if "tight" in v:
            L.append(f"- Cuts: tight {fmt(v['tight']['start'])}→{fmt(v['tight']['end'])} ({v['tight']['duration']}s) · "
                     f"long {fmt(v['long']['start'])}→{fmt(v['long']['end'])} ({v['long']['duration']}s)")
        b = p["breakdown"]
        L.append("- Score breakdown: " + ", ".join(f"{k} {v:+.1f}" for k, v in b.items()))
    q = run["quality"]
    L.append("")
    L.append("## Where the tool may pick badly")
    L.append("")
    L.append(f"{q['clean_promos']} of {len(run['promos'])} promos carry no warning flag.")
    L.append("")
    for k, v in q["flag_counts"].items():
        L.append(f"- **{k}** × {v['count']} — {v['meaning']}")
    L.append("")
    for fm in q["known_failure_modes"]:
        L.append(f"- *{fm['mode']}*: {fm['detail']}")
    if run.get("comparison"):
        c = run["comparison"]
        s = c["summary"]
        L.append("")
        L.append("## Your manual promos vs. the tool")
        L.append("")
        L.append(f"**{s['headline']}** Recall {s['recall']:.0%} · incl. partial {s['recall_incl_partial']:.0%} · "
                 f"Recall@10 {s['recall_at_k'].get('10')} · mean IoU {s['mean_iou_matched']} · "
                 f"mean start error {s['mean_abs_start_error_s']} s · mean end error {s['mean_abs_end_error_s']} s.")
        L.append("")
        L.append("| Manual | Your segments | Status | Tool promo | Tool segments | IoU | Δstart | Δend | Notes |")
        L.append("|---|---|---|---|---|---:|---:|---:|---|")
        for r in c["rows"]:
            ai = r.get("ai") or {}
            L.append(f"| {r['manual']['id']} | {_segs_md(r['manual']['segments'])} | **{r['status']}** | "
                     f"{(ai.get('id', '') + ' (#' + str(ai.get('rank')) + ')') if ai else '—'} | {_segs_md(ai.get('segments', [])) if ai else '—'} | "
                     f"{r['iou']:.2f} | {r['start_delta'] if r['start_delta'] is not None else '—'} | "
                     f"{r['end_delta'] if r['end_delta'] is not None else '—'} | {r['diagnosis']} |")
        if c["new_finds"]:
            L.append("")
            L.append(f"**Found by the tool but not in your list ({len(c['new_finds'])}):** " +
                     ", ".join(f"{n['id']} (#{n['rank']}, {_segs_md(n['segments'])})" for n in c["new_finds"][:12]))
    if run.get("warnings"):
        L.append("")
        L.append("## Input warnings")
        for w in run["warnings"][:50]:
            L.append(f"- {w}")
    L.append("")
    return "\n".join(L)


def save_outputs(run: dict, out_dir: str | Path, cfg: dict | None = None) -> dict[str, str]:
    from .editor_formats import edl_all, ffmpeg_script, markers_csv
    from .report_html import html_report
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pc = (cfg or {}).get("promo", {})
    pre, post = float(pc.get("pre_roll_seconds", 0.0)), float(pc.get("post_roll_seconds", 0.4))
    builders: dict[str, Any] = {
        "promos.json": lambda: to_json(run),            # first: the raw result survives even if a report fails
        "promos.csv": lambda: promos_csv(run),
        "editor_cut_sheet.csv": lambda: cut_sheet_csv(run, pre, post),
        "promos_report.md": lambda: markdown_report(run),
        "report.html": lambda: html_report(run),
        "promos.edl": lambda: edl_all(run, pre, post),
        "markers.csv": lambda: markers_csv(run),
        "ffmpeg_cuts.sh": lambda: ffmpeg_script(run, pre, post),
        "metrics.json": lambda: json.dumps(run.get("metrics", {}), indent=2, default=str),
    }
    if run.get("comparison"):
        builders["comparison_vs_manual.csv"] = lambda: comparison_csv(run)
    written, failed = {}, {}
    for name, build in builders.items():
        try:
            content = build()
            p = out / name
            p.write_text(content, encoding="utf-8")
            written[name] = str(p)
        except Exception as exc:  # noqa: BLE001 - one broken export must not block the others
            failed[name] = f"{type(exc).__name__}: {exc}"
    if failed:
        (out / "EXPORT_ERRORS.txt").write_text("\n".join(f"{k}: {v}" for k, v in failed.items()), encoding="utf-8")
        written["EXPORT_ERRORS.txt"] = str(out / "EXPORT_ERRORS.txt")
    return written
