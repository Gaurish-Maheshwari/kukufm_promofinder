import type { Promo } from "../types";
import { tc } from "../lib/format";

/** One track per segment: the whole episode, the cut highlighted (pink edge = IN/hook, teal edge = OUT/cliffhanger). */
export function TimelineBar({ promo, durations }: { promo: Promo; durations: Record<number, number> }) {
  return (
    <div className="strip" aria-label="Where the promo sits in its episode">
      {promo.segments.map((s, i) => {
        const d = Math.max(durations[s.episode] ?? s.end, s.end, 1);
        const left = (s.start / d) * 100;
        const width = Math.max(1.5, ((s.end - s.start) / d) * 100);
        const ticks = Array.from({ length: Math.floor(d / 30) }, (_, k) => ((k + 1) * 30 / d) * 100);
        return (
          <div key={i}>
            <div className="track">
              {ticks.map((t) => <span key={t} className="tick" style={{ left: `${t}%` }} />)}
              <span className="cut" style={{ left: `${left}%`, width: `${width}%` }} />
            </div>
            <div className="track-label"><span>Ep {s.episode} · 0:00</span><span>{tc(s.start)} → {tc(s.end)}</span><span>{tc(d)}</span></div>
          </div>
        );
      })}
    </div>
  );
}
