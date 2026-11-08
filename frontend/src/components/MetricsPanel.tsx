import type { RunResult } from "../types";
import { pct } from "../lib/format";

export function MetricsPanel({ run }: { run: RunResult }) {
  const m = run.metrics;
  const bc = m.brief_compliance, inp = m.input, out = m.output, div = m.diversity, ops = m.operations, q = m.quality;
  const tile = (k: string, v: string | number, d?: string) => (
    <div className="kpi" key={k}><div className="k">{k}</div><div className="v">{v}</div>{d && <div className="d">{d}</div>}</div>
  );
  return (
    <>
      <div className="section">
        <h3>Does it meet the brief?</h3>
        <div className="kpis">
          {tile("Length within window", pct(bc.duration_in_range), `${run.settings.min_seconds}–${run.settings.max_seconds} s`)}
          {tile("Hook in the first 3 s", pct(bc.hook_within_3s))}
          {tile("Strong cliffhanger", pct(bc.strong_cliffhanger))}
          {tile("Stands on its own", pct(bc.standalone_ok))}
          {tile("All three at once", pct(bc.all_three))}
        </div>
      </div>
      <div className="section">
        <h3>Output</h3>
        <div className="kpis">
          {tile("Promos", out.promos, `${out.montages} stitched`)}
          {tile("Candidates scored", out.candidates_scored)}
          {tile("Median length", `${out.duration_median_s ?? "—"} s`, `${out.duration_min_s}–${out.duration_max_s} s`)}
          {tile("Average score", q.mean_score ?? "—", `top 10: ${q.top10_mean_score}`)}
          {tile("Episodes in top 10", div.episodes_in_top10, `${div.tropes_in_top10} different tropes`)}
          {tile("Episodes covered", pct(div.episode_coverage), `${div.episodes_covered} of ${inp.episodes}`)}
        </div>
      </div>
      <div className="split">
        <div className="section">
          <h3>Input</h3>
          <div className="kpis">
            {tile("Episodes", inp.episodes, `${inp.show_minutes} min`)}
            {tile("Lines and actions", inp.beats, `${inp.scenes} scenes`)}
            {tile("Timestamped", pct(inp.timestamp_coverage), "others interpolated")}
            {tile("Characters", inp.characters)}
          </div>
        </div>
        <div className="section">
          <h3>Running cost</h3>
          <div className="kpis">
            {tile("Runtime", `${ops.runtime_s.toFixed(2)} s`, `${(ops.seconds_per_episode * 1000).toFixed(0)} ms per episode`)}
            {tile("LLM calls", ops.llm.calls, ops.llm.used ? `${ops.llm.provider} · ${ops.llm.model}` : "rules only")}
            {tile("Tokens", (ops.llm.input_tokens + ops.llm.output_tokens).toLocaleString(), `${ops.llm.cache_hits} cache hits`)}
          </div>
        </div>
      </div>
      <div className="section">
        <h3>Time per stage</h3>
        <div className="tablewrap"><table className="t"><tbody>
          {Object.entries(ops.stage_seconds as Record<string, number>).map(([k, v]) => <tr key={k}><td>{k}</td><td className="mono">{v.toFixed(3)} s</td></tr>)}
        </tbody></table></div>
      </div>
    </>
  );
}

export function QualityPanel({ run, onSelect }: { run: RunResult; onSelect: (id: string) => void }) {
  const q = run.quality;
  return (
    <>
      <div className="section">
        <p className="headline">{q.clean_promos} of {run.promos.length} promos carry no warning.</p>
        <p className="muted">Each warning names the specific way a pick might be bad. Check flagged promos before posting.</p>
      </div>
      <div className="split">
        <div className="section">
          <h3>Warnings in this run</h3>
          <div className="tablewrap"><table className="t"><tbody>
            {Object.entries(q.flag_counts).map(([k, v]) => <tr key={k}><td>{v.meaning}</td><td className="mono">{v.count}</td></tr>)}
            {Object.keys(q.flag_counts).length === 0 && <tr><td>No warnings.</td></tr>}
          </tbody></table></div>
        </div>
        <div className="section">
          <h3>Review these first</h3>
          <div className="tablewrap"><table className="t"><tbody>
            {q.review_first.map((r) => <tr key={r.id}><td><button className="btn sm" onClick={() => onSelect(r.id)}>{r.id} · #{r.rank}</button></td><td className="small">{r.flags.join("; ")}</td></tr>)}
          </tbody></table></div>
        </div>
      </div>
      <div className="section">
        <h3>Where rules-based picking goes wrong</h3>
        <div className="tablewrap"><table className="t"><tbody>
          {q.known_failure_modes.map((f) => <tr key={f.mode}><td><b>{f.mode}</b></td><td className="small">{f.detail}</td></tr>)}
        </tbody></table></div>
      </div>
      {(q.parse_issues.length > 0 || run.warnings.length > 0) && (
        <div className="section">
          <h3>Input warnings</h3>
          <ul className="small">
            {q.parse_issues.map((p) => <li key={p.episode}>Ep {p.episode}: {pct(p.confidence)} timestamped. {p.warnings.join(" ")}</li>)}
            {run.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
    </>
  );
}
