import type { Promo } from "../types";
import { FLAG_LABEL, KIND_LABEL } from "../lib/format";
import { TimelineBar } from "./TimelineBar";

interface Props { promos: Promo[]; selected: string | null; onSelect: (id: string) => void; durations: Record<number, number>; order: "rank" | "post" }

export function PromoList({ promos, selected, onSelect, durations, order }: Props) {
  const list = [...promos].sort((a, b) => (order === "rank" ? a.rank - b.rank : a.post_order - b.post_order));
  if (!list.length) return <p className="muted">No promo cleared the minimum score. Lower it in Settings.</p>;
  return (
    <div className="plist" role="list">
      {list.map((p) => (
        <button key={p.id} role="listitem" className="prow" aria-current={selected === p.id} onClick={() => onSelect(p.id)}>
          <div className="rank">{order === "rank" ? p.rank : p.post_order}<small>{order === "rank" ? `post ${p.post_order}` : `rank ${p.rank}`}</small></div>
          <div className="lines">
            <div className="seginfo">
              <b>{p.id}</b>
              <span>{p.duration.toFixed(1)} s</span>
              <span className="chip kind">{KIND_LABEL[p.kind]}</span>
              {p.source !== "rules" && <span className="chip">AI-judged</span>}
            </div>
            <TimelineBar promo={p} durations={durations} />
            <div className="beat"><span className="tag hook">Hook {p.hook.at.toFixed(1)}s</span><span className="txt">{p.hook.text}</span></div>
            <div className="beat"><span className="tag cliff">Cliffhanger</span><span className="txt">{p.cliffhanger.text}</span></div>
            <div className="why">{p.why}</div>
            {(p.tropes.length > 0 || p.flags.length > 0) && (
              <div className="chips">
                {p.tropes.slice(0, 3).map((t) => <span key={t} className="chip">{t.replace(/_/g, " ")}</span>)}
                {p.flags.map((f) => <span key={f} className="chip flag">{FLAG_LABEL[f] ?? f}</span>)}
              </div>
            )}
          </div>
          <div className="score">{p.score.toFixed(0)}<small>score</small></div>
        </button>
      ))}
    </div>
  );
}
