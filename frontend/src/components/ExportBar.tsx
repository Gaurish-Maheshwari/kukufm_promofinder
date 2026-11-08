import { useState } from "react";
import type { RunResult } from "../types";
import { api } from "../api";

const FORMATS: { id: string; label: string; who: string }[] = [
  { id: "cutsheet", label: "Editor cut sheet (CSV)", who: "Episode, IN/OUT in SMPTE timecode with handles, in posting order" },
  { id: "edl", label: "EDL (CMX3600)", who: "Import into Premiere, Resolve or Avid; every promo laid out on one timeline" },
  { id: "markers", label: "Markers (CSV)", who: "One marker per segment, for manual placement" },
  { id: "ffmpeg", label: "ffmpeg cut script", who: "Cuts raw preview clips if you have the episode videos" },
  { id: "html", label: "Shareable report (HTML)", who: "One file, opens in any browser" },
  { id: "md", label: "Report (Markdown)", who: "For docs and GitHub" },
  { id: "csv", label: "All promos (CSV)", who: "One row per segment with hook, cliffhanger, why, flags" },
  { id: "json", label: "Full result (JSON)", who: "Everything, including transcripts and metrics" },
  { id: "comparison", label: "Comparison vs. your picks (CSV)", who: "Only when manual promos were added" },
];

export function ExportBar({ run }: { run: RunResult }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const go = async (fmt: string) => {
    setBusy(fmt); setErr("");
    try { await api.download(fmt, run); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };
  return (
    <div className="tablewrap">
      <table className="t">
        <tbody>
          {FORMATS.filter((f) => f.id !== "comparison" || run.comparison).map((f) => (
            <tr key={f.id}>
              <td style={{ width: 260 }}><b>{f.label}</b></td>
              <td className="small muted">{f.who}</td>
              <td style={{ width: 120 }}><button className="btn sm" disabled={busy === f.id} onClick={() => go(f.id)}>{busy === f.id ? "Preparing" : "Download"}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {err && <div className="error">{err}</div>}
    </div>
  );
}
