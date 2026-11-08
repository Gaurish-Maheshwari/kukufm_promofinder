import { useState } from "react";
import type { Promo, RunResult } from "../types";
import { api } from "../api";
import { copy, segText, smpte, tc } from "../lib/format";
import { ScoreBreakdown } from "./ScoreBreakdown";

export function PromoDetail({ promo, run }: { promo: Promo; run: RunResult }) {
  const [toast, setToast] = useState("");
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 2200); };
  const send = async (verdict: "accept" | "reject") => {
    try {
      await api.feedback({ run_id: run.run_id, promo_id: promo.id, verdict, episode: promo.segments[0].episode, start: promo.segments[0].start, end: promo.segments[promo.segments.length - 1].end });
      flash(verdict === "accept" ? "Marked as a keeper" : "Marked as a miss");
    } catch (e) { flash(String((e as Error).message)); }
  };
  let seg = 0;
  return (
    <aside className="detail" aria-label={`Promo ${promo.id}`}>
      <div className="phone" aria-label="Clip as it plays, top to bottom">
        <span className="notch" />
        <div className="screen">
          {promo.transcript.filter((l) => l.kind !== "scene").map((l, i) => {
            const jump = l.segment !== seg && seg !== 0;
            seg = l.segment;
            return (
              <div key={i}>
                {jump && <div className="jump">cut to Ep {l.episode}</div>}
                <p className={`ln ${l.speaker ? "" : "act"} ${l.kind === "camera" ? "cam" : ""} ${l.kind === "sfx" ? "sfx" : ""} ${l.is_hook ? "hook" : ""} ${l.is_cliff ? "cliff" : ""}`}>
                  <span className="t">{tc(l.start)}</span>
                  {l.kind === "camera" && <span className="tag">Shot</span>}
                  {l.kind === "sfx" && <span className="tag">Sound</span>}
                  {l.speaker ? <><b>{l.speaker}</b>{l.manner ? <i> ({l.manner})</i> : null} {l.text}</> : l.text}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="panel">
        <h3>Cut points</h3>
        {promo.segments.map((s, i) => (
          <div className="tcrow" key={i}>
            <span>Ep {s.episode}{promo.segments.length > 1 ? ` · part ${i + 1}` : ""}</span>
            <span className="mono">{smpte(s.start)} → {smpte(s.end)}</span>
            <button className="btn sm" onClick={async () => flash((await copy(`Ep ${s.episode} ${smpte(s.start)} - ${smpte(s.end)}`)) ? "Copied" : "Copy failed")}>Copy</button>
          </div>
        ))}
        <div className="tcrow"><span>Whole promo</span><span className="mono">{promo.duration.toFixed(1)} s</span>
          <button className="btn sm" onClick={async () => flash((await copy(`${promo.id}: ${segText(promo.segments)} | hook: ${promo.hook.text} | cliffhanger: ${promo.cliffhanger.text}`)) ? "Copied" : "Copy failed")}>Copy all</button>
        </div>
        {promo.variants.tight && (
          <p className="hint">Other cuts of the same moment: tight {tc(promo.variants.tight.start)}–{tc(promo.variants.tight.end)} ({promo.variants.tight.duration}s), long {tc(promo.variants.long.start)}–{tc(promo.variants.long.end)} ({promo.variants.long.duration}s)</p>
        )}
        {toast && <div className="toast" role="status">{toast}</div>}
      </div>

      <div className="panel">
        <h3>Why this works</h3>
        <p style={{ marginTop: 0 }}>{promo.why}</p>
        {promo.hook.llm && <p className="small"><b style={{ color: "var(--hook)" }}>Hook (AI):</b> {promo.hook.llm}</p>}
        {promo.cliffhanger.llm && <p className="small"><b style={{ color: "var(--cliff)" }}>Cliffhanger (AI):</b> {promo.cliffhanger.llm}</p>}
        <p className="small muted">Posting: {promo.post_rationale}</p>
        {promo.llm_notes.standalone_reasons && promo.llm_notes.standalone_reasons.length > 0 && (
          <p className="small"><b>Context risks:</b> {promo.llm_notes.standalone_reasons.join("; ")}</p>
        )}
        {promo.llm_notes.refined && <p className="small muted">{promo.llm_notes.refined}</p>}
      </div>

      <div className="panel">
        <h3>Score {promo.score.toFixed(0)}{promo.llm_score != null && <span className="muted small"> · rules {promo.heuristic_score.toFixed(0)} / AI {promo.llm_score.toFixed(0)}</span>}</h3>
        <ScoreBreakdown breakdown={promo.breakdown} />
      </div>

      <div className="panel">
        <h3>Is this a keeper?</h3>
        <div className="feedback">
          <button className="btn sm" onClick={() => send("accept")}>Keep it</button>
          <button className="btn sm" onClick={() => send("reject")}>Not a promo</button>
        </div>
        <p className="hint">Your verdicts are saved and used by <span className="mono">promo-finder learn</span> to re-weight the scorer.</p>
      </div>
    </aside>
  );
}
