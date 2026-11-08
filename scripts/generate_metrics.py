#!/usr/bin/env python3
"""Run the test suite + benchmarks and (re)write METRICS.md.

    python scripts/generate_metrics.py                                   # sample show only
    python scripts/generate_metrics.py --input data/input \\
        --manual data/manual_promos/my_manual_promos.csv                 # + the real input pack vs. your picks

Sections: test results · metric definitions/targets · brief compliance · agreement
with manual promos · ablation (what each signal contributes) · parser robustness ·
scale & cost (50-episode run, LLM token projection) · failure cases.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from promo_engine.config import load_config  # noqa: E402
from promo_engine.ingest import load_inputs, parse_show  # noqa: E402
from promo_engine.llm.judge import _render_candidate  # noqa: E402
from promo_engine.llm.prompts import SYSTEM, USER_TEMPLATE  # noqa: E402
from promo_engine.pipeline import run_pipeline  # noqa: E402
from promo_engine.timecode import fmt  # noqa: E402

SAMPLE = ROOT / "data" / "sample"


def pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def run_tests() -> dict:
    junit = ROOT / ".cache" / "junit.xml"
    junit.parent.mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={junit}"], cwd=ROOT, capture_output=True, text=True)
    dur = time.perf_counter() - t
    root = ET.parse(junit).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    by_file: dict[str, list[int]] = {}
    for tc in suite.iter("testcase"):
        f = tc.get("classname", "").split(".")[-1]
        ok = not any(c.tag in ("failure", "error") for c in tc)
        by_file.setdefault(f, [0, 0])
        by_file[f][0 if ok else 1] += 1
    return {"tests": int(suite.get("tests")), "failures": int(suite.get("failures")), "errors": int(suite.get("errors")),
            "skipped": int(suite.get("skipped", 0)), "seconds": round(dur, 1), "by_file": by_file, "rc": proc.returncode}


def ablations(inp, manual) -> list[dict]:
    base = load_config(overrides={"use_learned_weights": False})
    base["use_learned_weights"] = False
    variants = {
        "Full scorer (default weights)": {},
        "Without hook signal": {"weights": {"hook": 0.0}},
        "Without cliffhanger signal": {"weights": {"cliffhanger": 0.0}},
        "Without stand-alone check": {"weights": {"standalone": 0.0}},
        "Without diversity (pure score order)": {"promo": {"mmr_lambda": 1.0, "max_per_episode": 99, "nms_iou": 0.9}},
        "Without stitched promos": {"promo": {"enable_montages": False}},
        "Hook + cliffhanger only": {"weights": {k: 0.0 for k in ("standalone", "intensity", "pace", "duration_fit", "trope", "episode_end", "spoiler_penalty")}},
    }
    out = []
    from promo_engine.config import deep_merge
    for name, ov in variants.items():
        cfg = deep_merge(copy.deepcopy(base), ov)
        r = run_pipeline(inp, cfg=cfg, manual=manual, use_llm=False)
        s = r.comparison["summary"] if r.comparison else {}
        bc = r.metrics["brief_compliance"]
        out.append({"name": name, "recall": s.get("recall"), "r10": s.get("recall_at_k", {}).get("10"),
                    "r5": s.get("recall_at_k", {}).get("5"), "iou": s.get("mean_iou_matched"),
                    "all_three": bc["all_three"], "promos": len(r.promos),
                    "eps_top10": r.metrics["diversity"]["episodes_in_top10"]})
    return out


def parser_robustness() -> list[dict]:
    fx = ROOT / "tests" / "fixtures"
    cases = [
        ("Bracketed `[00:00:07] NAME: line`, 2 episodes in one file", fx / "bracketed.txt", 2),
        ("Pipe table with header row and ranges", fx / "pipe_table.txt", 1),
        ("Classic layout (TC line / NAME / (paren) / dialogue)", fx / "classic.txt", 1),
        ("Lines without timestamps (interpolated)", fx / "untimed_lines.txt", 1),
        ("Show-absolute timestamps (shifted to 0)", fx / "absolute_times.txt", 1),
        ("Two episodes, no headers, clock resets", fx / "two_eps_no_headers.txt", 2),
        ("Subtitles (.srt)", fx / "subs.srt", 1),
        ("Sample: .txt bracketed (3 files)", [SAMPLE / "show" / f"Episode_0{i}.txt" for i in (1, 2, 3)], 3),
        ("Sample: .docx with untagged actions", SAMPLE / "show" / "more" / "Ep05.docx", 1),
        ("Sample: PDF, 2 episodes, running header + page numbers", SAMPLE / "show" / "Episodes_07-08.pdf", 2),
        ("Sample: full zip with nested zip + __MACOSX junk", SAMPLE / "sample_show.zip", 8),
        ("Kuku block layout (synthetic fixture): **LABEL (manner):** / Start–End line / text, metadata header, overlapping shots", fx / "block_format", 2),
    ]
    real = ROOT / "data" / "input"
    if any(p.suffix.lower() in (".txt", ".pdf", ".docx", ".zip") for p in real.rglob("*") if p.is_file() and p.name.lower() != "readme.md"):
        cases.append(("**Real input pack** (data/input)", real, None))
    rows = []
    for name, src, expected in cases:
        show = parse_show(load_inputs(src))
        content = sum(1 for e in show.episodes for b in e.beats if b.kind != "scene")
        timed = sum(1 for e in show.episodes for b in e.beats if b.kind != "scene" and b.timed)
        dlg = sum(1 for e in show.episodes for b in e.beats if b.kind == "dialogue" and b.speaker)
        rows.append({"case": name, "expected": expected if expected is not None else len(show.episodes), "found": len(show.episodes), "beats": content,
                     "dialogue_with_speaker": dlg, "timestamped": timed / content if content else 0})
    return rows


def synth_50(tmp: Path) -> Path:
    """50-episode show: the 8 sample episodes cycled and renumbered (same text, new numbers)."""
    from scripts_make import EPISODES, render_bracket  # type: ignore
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in range(1, 51):
            src = ((n - 1) % 8) + 1
            title, beats = EPISODES[src]
            z.writestr(f"show50/Episode_{n:02d}.txt", render_bracket(n, f"{title} ({n})", beats))
    p = tmp / "show50.zip"
    p.write_bytes(buf.getvalue())
    return p


def llm_projection(run) -> dict:
    """Prompt size for re-ranking the top N, measured on this run's real candidates (≈4 chars per token)."""
    cfg = run.cfg
    n, bs = int(cfg["llm"]["rerank_top_n"]), int(cfg["llm"]["batch_size"])
    pool = sorted(run.pool, key=lambda c: -c.score)[:n]
    chars = 0
    for k in range(0, len(pool), bs):
        blocks = [_render_candidate(f"c{i + 1}", c, run.show)[0] for i, c in enumerate(pool[k:k + bs])]
        chars += len(SYSTEM) + len(USER_TEMPLATE) + sum(len(b) for b in blocks) + 300
    calls = (len(pool) + bs - 1) // bs
    tin = chars / 4
    tout = calls * bs * 110
    return {"calls": calls, "input_tokens": int(tin), "output_tokens": int(tout), "candidates": len(pool)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="real input pack (folder/zip)")
    ap.add_argument("--manual", help="your manual promos for the real pack")
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args()

    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("scripts_make", ROOT / "scripts" / "make_sample_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["scripts_make"] = mod
    if not (SAMPLE / "sample_show.zip").exists():
        mod.main()

    print("running tests…", flush=True)
    tests = None if a.skip_tests else run_tests()
    print("sample run…", flush=True)
    sample = run_pipeline(SAMPLE / "sample_show.zip", manual=SAMPLE / "manual_promos_sample.csv", use_llm=False,
                          show_title="The Maid Who Owns the Mansion (sample)")
    print("ablations…", flush=True)
    abl = ablations(SAMPLE / "sample_show.zip", SAMPLE / "manual_promos_sample.csv")
    print("parser robustness…", flush=True)
    rob = parser_robustness()
    print("scale test…", flush=True)
    tmp = ROOT / ".cache"
    tmp.mkdir(exist_ok=True)
    z50 = synth_50(tmp)
    times = []
    for _ in range(3):
        t = time.perf_counter()
        r50 = run_pipeline(z50, use_llm=False)
        times.append(time.perf_counter() - t)
    proj = llm_projection(r50)
    real = None
    if a.input:
        print("real input pack…", flush=True)
        real = run_pipeline(a.input, manual=a.manual, use_llm=True)

    L: list[str] = []
    w = L.append
    w("# METRICS — test results and the numbers that matter")
    w("")
    w(f"_Generated {datetime.now():%Y-%m-%d %H:%M} by `python scripts/generate_metrics.py`. Re-run it after adding the real input pack "
      "and your manual promos: `python scripts/generate_metrics.py --input data/input --manual data/manual_promos/my_manual_promos.csv`._")
    w("")
    w("> **Honesty note.** " + ("The section *Real input pack* below is a run on Kuku's show. Brief-compliance numbers there "
      "measure the tool against its own thresholds (hook cue ≥ 0.4 in the first 3 s, cliffhanger ≥ 0.5, no context flags), so "
      "they show the picks are well-formed, not that they are the best promos. " if real is not None else "") +
      "Agreement numbers (recall, cut-point error) are only meaningful against an editor's independent picks: the sample show's "
      "manual promos were picked by the same person who wrote the rules, so treat them as a smoke test. Re-run with "
      "`--manual` and your own picks for the real benchmark.")
    w("")
    if real is not None:
        rm = real.metrics
        w("## Real input pack")
        w("")
        w(f"- {rm['input']['episodes']} episodes, {rm['input']['beats']} lines/actions, {pct(rm['input']['timestamp_coverage'])} timestamped, runtime {rm['operations']['runtime_s']:.1f}s, "
          f"LLM: {rm['operations']['llm']['provider'] or 'none'} ({rm['operations']['llm']['calls']} calls, {rm['operations']['llm']['input_tokens'] + rm['operations']['llm']['output_tokens']:,} tokens).")
        bc = rm["brief_compliance"]
        w(f"- Brief compliance: length {pct(bc['duration_in_range'])} · hook ≤3s {pct(bc['hook_within_3s'])} · strong cliffhanger {pct(bc['strong_cliffhanger'])} · stand-alone {pct(bc['standalone_ok'])} · all three {pct(bc['all_three'])}.")
        dv = rm["diversity"]
        w(f"- Output: {rm['output']['promos']} promos from {rm['output']['candidates_scored']} candidates, median {rm['output']['duration_median_s']} s; "
          f"{dv['episodes_in_top10']} episodes and {dv['tropes_in_top10']} tropes in the top 10; {pct(rm['quality']['flagged_share'])} carry a warning flag; "
          f"degraded stages: {', '.join(rm.get('degraded_stages') or []) or 'none'}.")
        w("")
        w("| Rank | Post | Cut | Len | Hook | Cliffhanger | Score | Flags |")
        w("|---:|---:|---|---:|---|---|---:|---|")
        for p in sorted(real.promos, key=lambda p: p.rank)[:10]:
            cut = " + ".join(f"Ep {s.episode} {fmt(s.start)}–{fmt(s.end)}" for s in p.segments)
            w(f"| {p.rank} | {p.post_order} | {cut} | {p.duration:.0f}s | {p.hook['type']}: {p.hook['text'][:70].replace('|', '/')} | "
              f"{p.cliffhanger['type']} | {p.score:.0f} | {', '.join(p.flags) or '—'} |")
        w("")
        if not real.comparison:
            w("_No manual promos supplied yet: add them with `--manual` to get recall, cut-point error and the side-by-side table._")
        if real.comparison:
            s = real.comparison["summary"]
            w(f"- **{s['headline']}** Recall {pct(s['recall'])}, incl. partial {pct(s['recall_incl_partial'])}, Recall@10 {pct(s['recall_at_k'].get('10'))}, "
              f"mean IoU {s['mean_iou_matched']}, start/end error {s['mean_abs_start_error_s']}s / {s['mean_abs_end_error_s']}s, hook agreement {pct(s['hook_agreement'])}.")
            w("")
            w("| Your promo | Status | Tool promo | IoU | Δstart | Δend | Diagnosis |")
            w("|---|---|---|---:|---:|---:|---|")
            for r in real.comparison["rows"]:
                ai = r.get("ai") or {}
                w(f"| {r['manual']['id']} | {r['status']} | {ai.get('id', '—')} {('#' + str(ai.get('rank'))) if ai else ''} | {r['iou']:.2f} | {r['start_delta'] if r['start_delta'] is not None else '—'} | {r['end_delta'] if r['end_delta'] is not None else '—'} | {r['diagnosis']} |")
        w("")

    w("## 1. Test suite")
    w("")
    if tests:
        status = "✅ all passing" if tests["failures"] == 0 and tests["errors"] == 0 else "❌ failures"
        w(f"**{tests['tests']} tests, {tests['failures']} failures, {tests['errors']} errors, {tests['skipped']} skipped — {status}** ({tests['seconds']} s).")
        w("")
        w("| Test file | What it covers | Passed | Failed |")
        w("|---|---|---:|---:|")
        cover = {
            "test_timecode": "Every timestamp format (mm:ss, hh:mm:ss, SRT, SMPTE frames, 1m23s), formatting",
            "test_ingest": "Folders, nested zips, junk files, episode numbering, 6 screenplay layouts, interpolation, PDF furniture",
            "test_analysis": "Hook / cliffhanger / resolution cues, false-positive guards, tropes, stand-alone penalties, characters",
            "test_ranking": "Brief constraints on every promo, beat-aligned cuts, rank/post order, overlap + episode caps, platform presets, learner",
            "test_compare": "IoU maths, one-to-one matching, miss diagnosis, manual CSV / JSON / free-text loading, sample recall",
            "test_llm": "Key → provider detection (15 cases), env overrides, JSON repair, cache, mock re-rank, guarded edits, outage fallback",
            "test_exports": "CSV rows, cut sheet handles/order, valid CMX3600 EDL, ffmpeg script, HTML/MD reports, full output folder",
            "test_api": "Health, sample run, all 9 exports, upload job flow, bad input errors, path sandbox, key masking, feedback",
            "test_e2e": "CLI run / parse / learn exactly as a user runs them",
            "test_block_format": "Kuku's block layout: every block timed, camera/action/SFX kinds, double parentheticals, metadata ≠ dialogue, overlaps, header-vs-filename numbering, alias merge",
            "test_robustness": "12 layout mutations, wrong/missing extensions, HTML/ODT, no timestamps, garbage, fallback reader, min-score relaxation, failing stage, failing export, corrupt config, bad regex, LLM fallback chain, circuit breaker",
        }
        for f, (ok, bad) in sorted(tests["by_file"].items()):
            w(f"| `{f}.py` | {cover.get(f, '')} | {ok} | {bad} |")
    else:
        w("_Skipped (`--skip-tests`)._")
    w("")

    w("## 2. Which metrics matter for a promo finder (and why)")
    w("")
    w("| Metric | Definition | Why it matters | Target |")
    w("|---|---|---|---|")
    w("| **Recall vs. editor** | Share of the editor's manual promos the tool also returns (time IoU ≥ 0.30 or ≥ 50% coverage) | The tool replaces an editor's pass; if it misses what they would post, it is not trusted | ≥ 70% overall, ≥ 50% in top 10 |")
    w("| **Recall@10** | Same, counting only the tool's top 10 | Editors review the top of the list first | ≥ 50% |")
    w("| **Cut-point error** | Mean \\|Δstart\\| and \\|Δend\\| in seconds on matched promos | Every second an editor re-trims is time the tool did not save | ≤ 5 s |")
    w("| **Hook ≤ 3 s** | Promo has a hook cue (≥ 0.4) that lands within 3 s of IN | Brief requirement #1 — the scroll-stop | 100% |")
    w("| **Strong cliffhanger** | Cliffhanger score ≥ 0.5 at OUT | Brief requirement #2 — drives the tap-through | ≥ 85% |")
    w("| **Stand-alone** | No `needs_context` flag (pronoun/back-reference/off-screen-name penalties) | Brief requirement #3 — new viewers | ≥ 85% |")
    w("| **Length compliance** | 20–60 s (or the platform preset) | Hard platform/brief constraint | 100% |")
    w("| **Diversity** | Distinct episodes and tropes in the top 10 | A week of posts should test different angles | ≥ 5 episodes |")
    w("| **Flagged share** | Promos with any quality warning | How much human review is still needed | trend ↓ |")
    w("| **Runtime & cost / show** | Seconds and LLM tokens per 50-episode show | Kuku releases shows weekly; must be ~free at volume | < 10 s rules; < $0.10 LLM |")
    w("| **Timestamp coverage** | Share of beats with explicit timestamps | Low coverage = interpolated IN/OUT points | ≥ 95% |")
    w("")

    m = sample.metrics
    bc = m["brief_compliance"]
    w("## 3. Results on the sample show (rules only, no API key)")
    w("")
    w(f"{m['input']['episodes']} episodes · {m['input']['beats']} beats · {pct(m['input']['timestamp_coverage'])} timestamped · "
      f"{m['output']['candidates_scored']} candidates scored → **{m['output']['promos']} promos** ({m['output']['montages']} stitched) in **{m['operations']['runtime_s']:.2f} s**.")
    w("")
    w("| Brief requirement | Result |")
    w("|---|---:|")
    w(f"| Length 20–60 s | {pct(bc['duration_in_range'])} |")
    w(f"| Hook within first 3 s | {pct(bc['hook_within_3s'])} |")
    w(f"| Strong cliffhanger at the cut | {pct(bc['strong_cliffhanger'])} |")
    w(f"| Stands on its own | {pct(bc['standalone_ok'])} |")
    w(f"| **All three at once** | **{pct(bc['all_three'])}** |")
    w("")
    w(f"Diversity: {m['diversity']['episodes_in_top10']} episodes and {m['diversity']['tropes_in_top10']} tropes in the top 10; "
      f"{pct(m['diversity']['episode_coverage'])} of episodes have at least one promo. Mean score {m['quality']['mean_score']} "
      f"(top 10: {m['quality']['top10_mean_score']}); {pct(m['quality']['flagged_share'])} of promos carry a warning flag.")
    w("")
    w("**Top 5 as ranked:**")
    w("")
    w("| Rank | Post | Cut | Hook | Cliffhanger | Score |")
    w("|---:|---:|---|---|---|---:|")
    for p in sorted(sample.promos, key=lambda p: p.rank)[:5]:
        cut = " + ".join(f"Ep {s.episode} {fmt(s.start)}–{fmt(s.end)}" for s in p.segments)
        w(f"| {p.rank} | {p.post_order} | {cut} | {p.hook['type']}: {p.hook['text'][:60]} | {p.cliffhanger['type']} | {p.score:.0f} |")
    w("")

    s = sample.comparison["summary"]
    w("## 4. Agreement with manual promos (sample)")
    w("")
    w(f"**{s['headline']}**")
    w("")
    w("| Metric | Value |")
    w("|---|---:|")
    w(f"| Recall (found / manual) | {pct(s['recall'])} ({s['matched']}/{s['manual_total']}) |")
    w(f"| Recall incl. partial overlaps | {pct(s['recall_incl_partial'])} |")
    w(f"| Recall@5 / @10 | {pct(s['recall_at_k'].get('5'))} / {pct(s['recall_at_k'].get('10'))} |")
    w(f"| Precision vs. manual (tool promos that match one of yours) | {pct(s['precision_vs_manual'])} |")
    w(f"| Mean IoU of matches | {s['mean_iou_matched']} |")
    w(f"| Mean \\|Δstart\\| / \\|Δend\\| | {s['mean_abs_start_error_s']} s / {s['mean_abs_end_error_s']} s |")
    w(f"| Hook agreement (tool hook inside your first 3 s ± 3 s) | {pct(s['hook_agreement'])} |")
    w(f"| New finds (tool promos not on the manual list) | {s['ai_new_finds']} |")
    w("")
    w("| Manual | Status | Tool | IoU | Δstart | Δend | Diagnosis |")
    w("|---|---|---|---:|---:|---:|---|")
    for r in sample.comparison["rows"]:
        ai = r.get("ai") or {}
        w(f"| {r['manual']['id']} | {r['status']} | {ai.get('id', '—')} {('#' + str(ai.get('rank'))) if ai else ''} | {r['iou']:.2f} | "
          f"{r['start_delta'] if r['start_delta'] is not None else '—'} | {r['end_delta'] if r['end_delta'] is not None else '—'} | {r['diagnosis']} |")
    w("")
    w("Precision vs. manual is low by design: the editor listed 10 promos, the tool returns more. "
      "\"New finds\" are not errors; they are candidates the editor did not shortlist.")
    w("")

    w("## 5. Ablation — what each signal contributes (sample, vs. manual promos)")
    w("")
    w("| Variant | Recall | Recall@5 | Recall@10 | Mean IoU | All-three compliance | Episodes in top 10 |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for r in abl:
        w(f"| {r['name']} | {pct(r['recall'])} | {pct(r['r5'])} | {pct(r['r10'])} | {r['iou']} | {pct(r['all_three'])} | {r['eps_top10']} |")
    w("")
    w("Read this as: if removing a signal does not change recall on the sample, the sample is too small to show its value. "
      "Re-run on the real 50 episodes and your picks to see which weights earn their place, then `promo-finder learn`.")
    w("")

    w("## 6. Parser robustness (input format is unknown in advance)")
    w("")
    w("| Input layout | Episodes expected | Found | Beats | Dialogue lines with speaker | Timestamped |")
    w("|---|---:|---:|---:|---:|---:|")
    for r in rob:
        ok = "✅" if r["expected"] == r["found"] else "❌"
        w(f"| {r['case']} | {r['expected']} | {r['found']} {ok} | {r['beats']} | {r['dialogue_with_speaker']} | {pct(r['timestamped'])} |")
    w("")

    med = sorted(times)[1]
    w("## 7. Scale and cost")
    w("")
    w(f"**50-episode show** (sample episodes cycled to 50, {r50.metrics['input']['beats']} beats, {r50.metrics['input']['show_minutes']} min of screen time): "
      f"rules-only pipeline median **{med:.2f} s** over 3 runs ({med / 50 * 1000:.0f} ms per episode), "
      f"{r50.metrics['output']['candidates_scored']} candidates scored → {len(r50.promos)} promos. Memory: tens of MB.")
    w("")
    w(f"**LLM re-rank cost** (measured prompt sizes for this 50-episode run, top {proj['candidates']} candidates, {proj['calls']} calls):")
    w(f"≈ {proj['input_tokens']:,} input + {proj['output_tokens']:,} output tokens per show.")
    w("")
    w("| Provider tier | Cost per show | Cost for 52 shows/year |")
    w("|---|---:|---:|")
    w("| Gemini / Groq / OpenRouter free tiers | $0 (within free daily limits) | $0 |")
    for name, pin, pout in (("Small paid model (~$0.15 / $0.60 per 1M tokens)", 0.15, 0.60), ("Mid model (~$1 / $4 per 1M)", 1.0, 4.0),
                            ("Frontier model (~$3 / $15 per 1M)", 3.0, 15.0)):
        c = proj["input_tokens"] / 1e6 * pin + proj["output_tokens"] / 1e6 * pout
        w(f"| {name} | ${c:.3f} | ${c * 52:.2f} |")
    w("")
    w("Prices are illustrative list-price bands for budgeting, not quotes; check the provider's page. "
      "Repeated runs on the same show cost $0 (disk cache keyed on provider + model + prompt).")
    w("")

    w("## 8. Where it picks badly (observed on the sample)")
    w("")
    flagged = [p for p in sorted(sample.promos, key=lambda p: p.rank) if p.flags]
    for p in flagged[:6]:
        cut = " + ".join(f"Ep {s.episode} {fmt(s.start)}–{fmt(s.end)}" for s in p.segments)
        w(f"- **{p.id}** ({cut}) — flags: {', '.join(p.flags)}. Hook: _{p.hook['text'][:70]}_")
    w("")
    missed = [r for r in sample.comparison["rows"] if r["status"] != "matched"]
    for r in missed:
        w(f"- Manual **{r['manual']['id']}** was {r['status']}: {r['diagnosis']}")
    w("- Cut points drift ~5–15 s from the editor's: the tool trims to the hook line, while editors often keep a few seconds of set-up before it. "
      "Use the **long** variant (shown per promo) when you want that set-up.")
    w("- Visual-only beats (a look, a silent reveal) and sarcasm are invisible to the rules; the optional LLM judge re-scores the top candidates to catch these.")
    w("")
    (ROOT / "METRICS.md").write_text("\n".join(L), encoding="utf-8")
    (ROOT / ".cache" / "metrics_summary.json").write_text(json.dumps({
        "tests": tests, "sample_metrics": sample.metrics, "ablation": abl, "parser": rob,
        "scale": {"episodes": 50, "median_s": med, "projection": proj}}, indent=2, default=str), encoding="utf-8")
    print("METRICS.md written.")
    return 0 if (tests is None or (tests["failures"] == 0 and tests["errors"] == 0)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
