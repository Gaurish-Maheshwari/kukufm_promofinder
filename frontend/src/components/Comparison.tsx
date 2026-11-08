import type { RunResult } from "../types";
import { pct, segText } from "../lib/format";

export function Comparison({ run, onSelect }: { run: RunResult; onSelect: (id: string) => void }) {
  const c = run.comparison;
  if (!c) {
    return (
      <div className="empty" style={{ marginTop: 20 }}>
        <h2>Line up your own picks</h2>
        <p>Add your manual promos in the left panel (CSV template, a Google Sheet exported as CSV, or plain notes like
          “Ep 3 00:41–01:15”) and run again. You’ll see which of yours the tool found, how far its cut points are from
          yours, and why it missed the rest.</p>
      </div>
    );
  }
  const s = c.summary;
  return (
    <>
      <div className="section">
        <p className="headline">{s.headline}</p>
        <p className="muted small">A promo counts as found when the tool's clip overlaps yours by at least 30% (time IoU), or covers at least half of yours.</p>
      </div>
      <div className="kpis">
        <div className="kpi"><div className="k">Found (recall)</div><div className="v">{pct(s.recall)}</div><div className="d">{s.matched} of {s.manual_total}</div></div>
        <div className="kpi"><div className="k">Including partial overlaps</div><div className="v">{pct(s.recall_incl_partial)}</div><div className="d">{s.partial} partial</div></div>
        <div className="kpi"><div className="k">Found in the top 10</div><div className="v">{pct(s.recall_at_k["10"])}</div><div className="d">top 5: {pct(s.recall_at_k["5"])}</div></div>
        <div className="kpi"><div className="k">Overlap when found</div><div className="v">{s.mean_iou_matched?.toFixed(2) ?? "—"}</div><div className="d">time IoU, 1.0 = identical</div></div>
        <div className="kpi"><div className="k">Cut-point drift</div><div className="v">{s.mean_abs_start_error_s ?? "—"}s / {s.mean_abs_end_error_s ?? "—"}s</div><div className="d">start / end, average</div></div>
        <div className="kpi"><div className="k">New finds</div><div className="v">{s.ai_new_finds}</div><div className="d">tool picks not on your list</div></div>
      </div>
      <div className="section">
        <h3>Side by side</h3>
        <div className="tablewrap">
          <table className="t">
            <thead><tr><th>Yours</th><th>Your cut</th><th>Result</th><th>Tool</th><th>Tool cut</th><th>IoU</th><th>Δ start / end</th><th>What happened</th></tr></thead>
            <tbody>
              {c.rows.map((r) => (
                <tr key={r.manual.id}>
                  <td><b>{r.manual.id}</b>{r.manual.hook && <div className="small muted">{r.manual.hook}</div>}</td>
                  <td className="mono small">{segText(r.manual.segments)}</td>
                  <td><span className={`status ${r.status}`}>{r.status === "matched" ? "Found" : r.status === "partial" ? "Partial" : "Missed"}</span></td>
                  <td>{r.ai ? <button className="btn sm" onClick={() => onSelect(r.ai!.id)}>{r.ai.id} · #{r.ai.rank}</button> : "—"}</td>
                  <td className="mono small">{r.ai ? segText(r.ai.segments) : "—"}</td>
                  <td className="mono">{r.iou.toFixed(2)}</td>
                  <td className="mono small">{r.start_delta ?? "—"} / {r.end_delta ?? "—"}</td>
                  <td className="small">{r.diagnosis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {c.new_finds.length > 0 && (
        <div className="section">
          <h3>Found by the tool, not on your list</h3>
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Promo</th><th>Cut</th><th>Hook</th><th>Why</th></tr></thead>
              <tbody>
                {c.new_finds.map((n) => (
                  <tr key={n.id}>
                    <td><button className="btn sm" onClick={() => onSelect(n.id)}>{n.id} · #{n.rank}</button></td>
                    <td className="mono small">{segText(n.segments)}</td>
                    <td className="small">{n.hook}</td>
                    <td className="small">{n.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
