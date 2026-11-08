const LABEL: Record<string, string> = {
  hook: "Hook", cliffhanger: "Cliffhanger", standalone: "Stand-alone", intensity: "Intensity", pace: "Pace",
  duration_fit: "Length fit", trope: "Trope", episode_end: "Episode end", spoiler_penalty: "Spoiler risk", montage_penalty: "Stitching",
};

export function ScoreBreakdown({ breakdown }: { breakdown: Record<string, number> }) {
  const max = Math.max(...Object.values(breakdown).map(Math.abs), 1);
  return (
    <div className="bars">
      {Object.entries(breakdown).map(([k, v]) => (
        <div key={k} className={`bar ${v < 0 ? "neg" : ""}`}>
          <span>{LABEL[k] ?? k}</span>
          <span className="b"><i style={{ width: `${(Math.abs(v) / max) * 100}%` }} /></span>
          <span className="v">{v > 0 ? "+" : ""}{v.toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}
