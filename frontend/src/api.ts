import type { Health, Options, RunResult } from "./types";

const BASE = (import.meta as any).env?.VITE_API_BASE ?? "";

async function asJson<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch { /* not json */ }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

function cleanOptions(o: Options) {
  return {
    platform: o.platform, top_k: o.top_k, min_score: o.min_score, max_per_episode: o.max_per_episode,
    enable_montages: o.enable_montages, use_llm: o.use_llm, llm_key: o.llm_key || null, show_title: o.show_title || null,
  };
}

export const api = {
  health: () => fetch(`${BASE}/api/health`).then((r) => asJson<Health>(r)),

  checkKey: (key: string, ping = false) =>
    fetch(`${BASE}/api/llm/check`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key, ping }) })
      .then((r) => asJson<any>(r)),

  /** Upload files (and optional manual promos), poll the job until it finishes. */
  async analyze(files: File[], manual: File | null, opts: Options, onProgress: (stage: string, frac: number) => void): Promise<RunResult> {
    const fd = new FormData();
    for (const f of files) fd.append("files", f, (f as any).webkitRelativePath || f.name);
    if (manual) fd.append("manual", manual, manual.name);
    fd.append("options", JSON.stringify(cleanOptions(opts)));
    let job = await fetch(`${BASE}/api/jobs`, { method: "POST", body: fd }).then((r) => asJson<any>(r));
    let misses = 0;
    const started = Date.now();
    while (job.status !== "done" && job.status !== "error") {
      onProgress(job.stage ?? "Working", job.progress ?? 0);
      await new Promise((res) => setTimeout(res, 500 + misses * 500));
      try {
        job = await fetch(`${BASE}/api/jobs/${job.id}`).then((r) => asJson<any>(r));
        misses = 0;
      } catch (e) {
        // a network blip or a busy server should not lose a long run: retry a few times
        if (++misses > 6) throw new Error(`Lost contact with the server while it was working (${(e as Error).message}). Try again.`);
      }
      if (Date.now() - started > 15 * 60 * 1000) throw new Error("The run took longer than 15 minutes. Try rules only, or a smaller batch.");
    }
    if (job.status === "error") throw new Error(job.error || "Analysis failed");
    onProgress("Done", 1);
    return job.result as RunResult;
  },

  sample: (opts: Options, withManual = true) =>
    fetch(`${BASE}/api/analyze/sample`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ with_manual: withManual, options: cleanOptions(opts) }),
    }).then((r) => asJson<RunResult>(r)),

  serverFolder: (path: string, manualPath: string | null, opts: Options) =>
    fetch(`${BASE}/api/analyze/path`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, manual_path: manualPath || null, options: cleanOptions(opts) }),
    }).then((r) => asJson<RunResult>(r)),

  /** Stateless export: the run we already hold is posted back and returned as a file. */
  async download(fmt: string, run: RunResult) {
    const r = await fetch(`${BASE}/api/export/${fmt}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(run) });
    if (!r.ok) throw new Error(`Export failed (${r.status})`);
    const blob = await r.blob();
    const cd = r.headers.get("Content-Disposition") || "";
    const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? `promos.${fmt}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  },

  feedback: (body: { run_id: string; promo_id: string; verdict: "accept" | "reject" | "adjust"; episode?: number; start?: number; end?: number; note?: string }) =>
    fetch(`${BASE}/api/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then((r) => asJson<{ ok: boolean; stored: number }>(r)),

  template: () => fetch(`${BASE}/api/template/manual`).then((r) => r.text()),
};
