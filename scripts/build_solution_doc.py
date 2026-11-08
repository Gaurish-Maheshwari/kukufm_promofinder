#!/usr/bin/env python3
"""Build docs/Solution_Doc.pdf (≤ 2 pages) from docs/solution_doc.md.

{{placeholders}} are filled from the latest run: outputs/raw_outputs_full_pack/promos.json
if it exists (the real input pack), else outputs/raw_outputs_sample/promos.json.
PDF rendering uses Playwright/Chromium when available; otherwise an HTML file is
written for you to print to PDF from a browser (Cmd+P ▸ Save as PDF).
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "solution_doc.md"
OUT_HTML = ROOT / "docs" / "Solution_Doc.html"
OUT_PDF = ROOT / "docs" / "Solution_Doc.pdf"


def pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def tokens() -> dict:
    full = ROOT / "outputs" / "raw_outputs_full_pack" / "promos.json"
    sample = ROOT / "outputs" / "raw_outputs_sample" / "promos.json"
    src = full if full.exists() else sample
    run = json.loads(src.read_text(encoding="utf-8"))
    m = run["metrics"]
    bc = m["brief_compliance"]
    c = (run.get("comparison") or {}).get("summary") or {}
    label = "real input pack" if src == full else "synthetic 8-episode sample; real-pack numbers after `run_full_pack.sh`"
    top = sorted(run["promos"], key=lambda p: p["rank"])[:3]
    top3 = "; ".join(
        f"#{p['rank']} " + " + ".join(f"Ep {s['episode']} {int(s['start'] // 60):02d}:{s['start'] % 60:04.1f}–{int(s['end'] // 60):02d}:{s['end'] % 60:04.1f}" for s in p["segments"])
        + f" ({p['hook']['type'].lower()} → {p['cliffhanger']['type'].lower()})" for p in top)
    return {
        "data_label": label,
        "episodes": m["input"]["episodes"], "beats": m["input"]["beats"], "promos": m["output"]["promos"],
        "runtime": f"{m['operations']['runtime_s']:.2f} s",
        "length": pct(bc["duration_in_range"]), "hook3": pct(bc["hook_within_3s"]),
        "cliff": pct(bc["strong_cliffhanger"]), "standalone": pct(bc["standalone_ok"]),
        "headline": c.get("headline", "Add your manual promos to measure agreement"),
        "recall": pct(c.get("recall")), "recall10": pct((c.get("recall_at_k") or {}).get("10")),
        "iou": c.get("mean_iou_matched", "—"),
        "start_err": f"{c['mean_abs_start_error_s']} s" if c.get("mean_abs_start_error_s") is not None else "—",
        "end_err": f"{c['mean_abs_end_error_s']} s" if c.get("mean_abs_end_error_s") is not None else "—",
        "top3": top3,
    }


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def md_to_html(md: str) -> str:
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            out.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s:\-|]+\|$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            t = "<table>" + "".join("<tr>" + "".join((f"<th>{inline(c)}</th>" if r == 0 else f"<td>{inline(c)}</td>") for c in row) + "</tr>"
                                    for r, row in enumerate(rows)) + "</table>"
            out.append(t)
            continue
        elif re.match(r"^\d+\. ", ln):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                items.append(f"<li>{inline(re.sub(r'^\d+\. ', '', lines[i]))}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 11mm 13mm; }
body { font: {fs}px/1.36 "Helvetica Neue", Helvetica, Arial, sans-serif; color: #17192c; }
h1 { font-size: {h1}px; margin: 0 0 3px; } h2 { font-size: {h2}px; margin: 8px 0 3px; color: #17192c; border-bottom: 1.5px solid #e0367a; padding-bottom: 1px; }
p { margin: 3px 0; } ul, ol { margin: 2px 0 2px 16px; padding: 0; } li { margin: 1px 0; }
table { border-collapse: collapse; width: 100%; margin: 4px 0; font-size: {tfs}px; } th, td { border-bottom: 1px solid #dadce5; padding: 2px 5px; text-align: left; }
th { background: #f2f3f7; } code { font-size: 0.92em; background: #f2f3f7; padding: 0 2px; } b { color: #000; }
"""


def build(fs: float) -> str:
    md = SRC.read_text(encoding="utf-8")
    for k, v in tokens().items():
        md = md.replace("{{" + k + "}}", str(v))
    css = CSS.replace("{fs}", f"{fs}").replace("{h1}", f"{fs + 6}").replace("{h2}", f"{fs + 2}").replace("{tfs}", f"{fs - 0.5}")
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Solution Doc</title><style>{css}</style></head><body>{md_to_html(md)}</body></html>"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        OUT_HTML.write_text(build(10.0), encoding="utf-8")
        print(f"Playwright not installed. Open {OUT_HTML} in a browser and Print ▸ Save as PDF (A4).")
        return 0
    from pypdf import PdfReader
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for fs in (12.5, 12.0, 11.5, 11.0, 10.5, 10.0, 9.6, 9.2, 8.8):
            page.set_content(build(fs))
            page.pdf(path=str(OUT_PDF), format="A4", print_background=True,
                     margin={"top": "11mm", "bottom": "11mm", "left": "13mm", "right": "13mm"})
            n = len(PdfReader(str(OUT_PDF)).pages)
            if n <= 2:
                break
        browser.close()
    OUT_HTML.write_text(build(fs), encoding="utf-8")
    print(f"{OUT_PDF} written: {n} page(s) at {fs}px.")
    return 0 if n <= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
