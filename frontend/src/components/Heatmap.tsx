import type { RunResult } from "../types";

/** Episodes × time: darker cells are more intense beats; bars under a row are the selected promos. */
export function Heatmap({ run, onSelect }: { run: RunResult; onSelect: (id: string) => void }) {
  const rows = run.heatmap;
  if (!rows.length) return null;
  const maxBins = Math.max(...rows.map((r) => r.values.length));
  const cw = 26, ch = 20, left = 52;
  const w = left + maxBins * cw + 8;
  const h = rows.length * ch + 22;
  const bin = rows[0].bin_seconds;
  const marks: Record<number, { s: number; e: number; id: string; rank: number }[]> = {};
  run.promos.forEach((p) => p.segments.forEach((s) => (marks[s.episode] ||= []).push({ s: s.start, e: s.end, id: p.id, rank: p.rank })));
  return (
    <div className="heat">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ maxWidth: w, display: "block" }} role="img" aria-label="Drama intensity by episode and time">
        {rows.map((r, i) => (
          <g key={r.episode} transform={`translate(0 ${i * ch})`}>
            <text x={0} y={11}>Ep {r.episode}</text>
            {r.values.map((v, k) => (
              <rect key={k} x={left + k * cw} y={0} width={cw - 1.5} height={ch - 7} rx={1.5} fill="var(--hook)" fillOpacity={0.06 + 0.94 * v}>
                <title>{`Ep ${r.episode}, ${k * bin}–${(k + 1) * bin}s · intensity ${v.toFixed(2)}`}</title>
              </rect>
            ))}
            {(marks[r.episode] || []).map((m) => (
              <line key={m.id + m.s} x1={left + (m.s / bin) * cw} x2={left + (m.e / bin) * cw} y1={ch - 3.5} y2={ch - 3.5}
                stroke="var(--cliff)" strokeWidth={3} style={{ cursor: "pointer" }} onClick={() => onSelect(m.id)}>
                <title>{`${m.id} (rank ${m.rank}) · click to open`}</title>
              </line>
            ))}
          </g>
        ))}
        <text x={left} y={h - 4}>0 s</text>
        <text x={left + maxBins * cw - 34} y={h - 4}>{maxBins * bin} s</text>
      </svg>
      <div className="legend">
        <span><span className="sw" style={{ background: "linear-gradient(90deg, color-mix(in srgb, var(--hook) 8%, transparent), var(--hook))" }} />Quiet to intense, per {bin}s</span>
        <span><span className="sw" style={{ background: "var(--cliff)", height: 3 }} />Selected promo (click to open)</span>
      </div>
    </div>
  );
}
