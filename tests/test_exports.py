import csv
import io
import re

from promo_engine.export import cut_sheet_csv, edl_all, ffmpeg_script, html_report, markdown_report, promos_csv, save_outputs


def test_csv_has_one_row_per_segment(sample_run):
    run = sample_run.to_dict()
    rows = list(csv.DictReader(io.StringIO(promos_csv(run))))
    assert len(rows) == sum(len(p["segments"]) for p in run["promos"])
    assert {"rank", "episode", "start", "end", "hook", "cliffhanger", "why"} <= set(rows[0])


def test_cut_sheet_handles_and_order(sample_run):
    run = sample_run.to_dict()
    rows = list(csv.DictReader(io.StringIO(cut_sheet_csv(run, pre_roll=0.5, post_roll=0.5))))
    assert [int(r["post_order"]) for r in rows] == sorted(int(r["post_order"]) for r in rows)
    r0 = rows[0]
    assert re.fullmatch(r"\d\d:\d\d:\d\d:\d\d", r0["in_tc"])
    p = next(p for p in run["promos"] if p["id"] == r0["promo_id"])
    assert abs(float(r0["in_s"]) - max(0, p["segments"][0]["start"] - 0.5)) < 1e-6


def test_edl_is_valid_cmx3600(sample_run):
    edl = edl_all(sample_run.to_dict())
    events = [l for l in edl.splitlines() if re.match(r"^\d{3}\s", l)]
    assert edl.startswith("TITLE:") and "FCM: NON-DROP FRAME" in edl
    assert len(events) == sum(len(p.segments) for p in sample_run.promos)
    for ev in events:
        parts = ev.split()
        assert re.fullmatch(r"EP\d{3}", parts[1])
        tcs = parts[-4:]
        assert all(re.fullmatch(r"\d\d:\d\d:\d\d:\d\d", t) for t in tcs)


def test_ffmpeg_and_reports(sample_run):
    run = sample_run.to_dict()
    sh = ffmpeg_script(run)
    assert sh.startswith("#!/usr/bin/env bash") and sh.count("ffmpeg ") >= len(run["promos"])
    md = markdown_report(run)
    assert "## Ranked promos" in md and "## Your manual promos vs. the tool" in md
    html = html_report(run)
    assert html.startswith("<!doctype html>") and "<svg" in html


def test_save_outputs_writes_everything(sample_run, tmp_path):
    files = save_outputs(sample_run.to_dict(), tmp_path, sample_run.cfg)
    for name in ("promos.json", "promos.csv", "editor_cut_sheet.csv", "promos_report.md", "report.html", "promos.edl",
                 "markers.csv", "ffmpeg_cuts.sh", "metrics.json", "comparison_vs_manual.csv"):
        assert (tmp_path / name).stat().st_size > 50, name
