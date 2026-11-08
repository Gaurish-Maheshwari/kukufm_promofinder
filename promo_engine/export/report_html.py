"""Self-contained, shareable HTML report (no external assets)."""
from __future__ import annotations

import html

from ..timecode import fmt

CSS = """
:root{--bg:#f7f5f0;--card:#fff;--ink:#1d1b18;--muted:#6b665d;--line:#e6e1d6;--acc:#d9480f;--ok:#2b8a3e;--warn:#e67700;--bad:#c92a2a}
@media (prefers-color-scheme:dark){:root{--bg:#141311;--card:#1d1c19;--ink:#f1ede4;--muted:#a39d91;--line:#2f2d28;--acc:#ff8a4c;--ok:#69db7c;--warn:#ffc078;--bad:#ff8787}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Inter,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:28px 16px 80px}h1{font-size:28px;margin:0 0 4px}h2{margin:36px 0 12px;font-size:20px}
.muted{color:var(--muted)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}.kpi b{display:block;font-size:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:10px 0}
.row{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}.rank{font-size:22px;font-weight:700;color:var(--acc);min-width:40px}
.tc{font-family:ui-monospace,Menlo,monospace;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:1px 6px}
.chip{display:inline-block;font-size:12px;border:1px solid var(--line);border-radius:99px;padding:1px 8px;margin:2px 4px 2px 0}
.flag{color:var(--warn)}table{width:100%;border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
.matched{color:var(--ok);font-weight:600}.partial{color:var(--warn);font-weight:600}.missed{color:var(--bad);font-weight:600}
details summary{cursor:pointer;color:var(--muted)}.tr{font-size:13px;margin:6px 0 0;padding-left:0;list-style:none}.tr li{padding:2px 0}
.hl{background:rgba(217,72,15,.12);border-radius:4px}.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
svg text{fill:var(--muted);font-size:10px}
"""


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _heatmap_svg(run: dict) -> str:
    rows = run.get("heatmap") or []
    if not rows:
        return ""
    maxbins = max(len(r["values"]) for r in rows)
    cw, ch, left = 9, 12, 44
    w = left + maxbins * cw + 10
    h = len(rows) * ch + 24
    promo_marks = {}
    for p in run["promos"]:
        for s in p["segments"]:
            promo_marks.setdefault(s["episode"], []).append((s["start"], s["end"], p["rank"]))
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Drama intensity heatmap">']
    for i, r in enumerate(rows):
        y = i * ch
        out.append(f'<text x="0" y="{y + 9}">Ep {r["episode"]}</text>')
        for k, v in enumerate(r["values"]):
            a = 0.08 + 0.92 * v
            out.append(f'<rect x="{left + k * cw}" y="{y}" width="{cw - 1}" height="{ch - 2}" fill="rgb(217,72,15)" fill-opacity="{a:.2f}"><title>Ep {r["episode"]} {k * r["bin_seconds"]:.0f}s: {v:.2f}</title></rect>')
        for s, e, rank in promo_marks.get(r["episode"], []):
            x1 = left + s / r["bin_seconds"] * cw
            x2 = left + e / r["bin_seconds"] * cw
            out.append(f'<line x1="{x1:.1f}" x2="{x2:.1f}" y1="{y + ch - 1.5}" y2="{y + ch - 1.5}" stroke="currentColor" stroke-width="2"><title>Promo #{rank}</title></line>')
    out.append(f'<text x="{left}" y="{h - 4}">0s</text><text x="{left + maxbins * cw - 30}" y="{h - 4}">{maxbins * rows[0]["bin_seconds"]:.0f}s</text></svg>')
    return "".join(out)


def html_report(run: dict) -> str:
    m = run["metrics"]
    bc = m["brief_compliance"]
    P: list[str] = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                    f"<title>Promo Report</title><style>{CSS}</style></head><body><main>"]
    llm = run["settings"].get("llm", {})
    P.append(f"<h1>{_e(run['show']['title'])} — promo report</h1>")
    P.append(f"<div class='muted'>Run {_e(run['run_id'])} · {_e(run['created_at'])} · platform {_e(run['settings']['platform'])} · "
             f"ranking: {'rules + ' + _e(llm.get('provider')) + ' / ' + _e(llm.get('model')) if llm.get('enabled') else 'rules only'}</div>")
    k = [("Episodes", m["input"]["episodes"]), ("Promos", m["output"]["promos"]), ("Hook ≤3s", f"{bc['hook_within_3s']:.0%}"),
         ("Strong cliffhanger", f"{bc['strong_cliffhanger']:.0%}"), ("In 20–60s", f"{bc['duration_in_range']:.0%}"),
         ("Episodes in top 10", m["diversity"]["episodes_in_top10"]), ("Runtime", f"{m['operations']['runtime_s']:.1f}s")]
    if run.get("comparison"):
        s = run["comparison"]["summary"]
        k.insert(2, ("Your promos found", f"{s['matched']}/{s['manual_total']}"))
    P.append("<div class='kpis'>" + "".join(f"<div class='kpi'><span class='muted'>{_e(a)}</span><b>{_e(b)}</b></div>" for a, b in k) + "</div>")
    P.append("<h2>Drama intensity across the show</h2><div class='card'>" + _heatmap_svg(run) +
             "<div class='muted'>Darker = more intense beats. Lines under a row = selected promos.</div></div>")
    P.append("<h2>Ranked promos</h2>")
    for p in run["promos"]:
        segs = " + ".join(f"Ep {s['episode']} <span class='tc'>{fmt(s['start'])} → {fmt(s['end'])}</span>" for s in p["segments"])
        flags = "".join(f"<span class='chip flag'>⚠ {_e(f)}</span>" for f in p["flags"])
        tropes = "".join(f"<span class='chip'>{_e(t)}</span>" for t in p["tropes"][:4])
        tr = "".join(
            f"<li class='{'hl' if r['is_hook'] or r['is_cliff'] else ''}'><span class='tc'>{fmt(r['start'])}</span> "
            f"{'<b>' + _e(r['speaker']) + ':</b> ' if r['speaker'] else '<i>'}{_e(r['text'])}{'' if r['speaker'] else '</i>'}"
            f"{' ← HOOK' if r['is_hook'] else ''}{' ← CLIFFHANGER' if r['is_cliff'] else ''}</li>" for r in p["transcript"])
        P.append(f"<div class='card'><div class='row'><span class='rank'>#{p['rank']}</span><b>{_e(p['id'])}</b>"
                 f"<span class='muted'>score {p['score']:.0f} · post #{p['post_order']} · {p['duration']:.1f}s · {_e(p['kind'].replace('_', ' '))}</span></div>"
                 f"<div class='bar'><i style='width:{min(100, p['score']):.0f}%'></i></div>"
                 f"<p>{segs}</p><p><b>Hook</b> ({_e(p['hook'].get('type'))}, {p['hook'].get('at', 0):.1f}s): {_e(p['hook'].get('text'))}<br>"
                 f"<b>Cliffhanger</b> ({_e(p['cliffhanger'].get('type'))}): {_e(p['cliffhanger'].get('text'))}<br>"
                 f"<b>Why it works:</b> {_e(p['why'])}</p><div>{tropes}{flags}</div>"
                 f"<details><summary>Transcript</summary><ul class='tr'>{tr}</ul></details></div>")
    P.append("<h2>Posting plan</h2><div class='card'><ol>" +
             "".join(f"<li><b>{_e(r['id'])}</b> — {_e(r['rationale'])}</li>" for r in run["posting_plan"]) + "</ol></div>")
    if run.get("comparison"):
        c = run["comparison"]
        s = c["summary"]
        P.append(f"<h2>Your manual promos vs. the tool</h2><p><b>{_e(s['headline'])}</b> Recall {s['recall']:.0%} · "
                 f"mean IoU {_e(s['mean_iou_matched'])} · start error {_e(s['mean_abs_start_error_s'])} s · end error {_e(s['mean_abs_end_error_s'])} s</p>")
        P.append("<div class='card' style='overflow-x:auto'><table><tr><th>Manual</th><th>Your segments</th><th>Status</th><th>Tool</th><th>Tool segments</th><th>IoU</th><th>Notes</th></tr>")
        for r in c["rows"]:
            ai = r.get("ai") or {}
            ms = "<br>".join(f"Ep {x['episode']} {fmt(x['start'])}→{fmt(x['end'])}" for x in r["manual"]["segments"])
            as_ = "<br>".join(f"Ep {x['episode']} {fmt(x['start'])}→{fmt(x['end'])}" for x in ai.get("segments", []))
            P.append(f"<tr><td>{_e(r['manual']['id'])}</td><td class='tc'>{ms}</td><td class='{r['status']}'>{r['status']}</td>"
                     f"<td>{_e(ai.get('id', '—'))}{(' #' + str(ai.get('rank'))) if ai else ''}</td><td class='tc'>{as_ or '—'}</td>"
                     f"<td>{r['iou']:.2f}</td><td>{_e(r['diagnosis'])}</td></tr>")
        P.append("</table></div>")
    q = run["quality"]
    P.append("<h2>Where the tool may pick badly</h2><div class='card'><ul>" +
             "".join(f"<li><b>{_e(k)}</b> × {v['count']} — {_e(v['meaning'])}</li>" for k, v in q["flag_counts"].items()) +
             "</ul><ul>" + "".join(f"<li><i>{_e(f['mode'])}</i>: {_e(f['detail'])}</li>" for f in q["known_failure_modes"]) + "</ul></div>")
    P.append("</main></body></html>")
    return "".join(P)
