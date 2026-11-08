import { useState } from "react";
import type { Health, Options } from "../types";
import { api } from "../api";

const PLATFORMS: { id: Options["platform"]; label: string; hint: string }[] = [
  { id: "any", label: "Any", hint: "20–60 s" },
  { id: "tiktok", label: "TikTok", hint: "20–35 s" },
  { id: "reels", label: "Reels", hint: "25–45 s" },
  { id: "shorts", label: "Shorts", hint: "30–60 s" },
];

export function SettingsPanel({ opts, setOpts, health }: { opts: Options; setOpts: (o: Options) => void; health: Health | null }) {
  const [detected, setDetected] = useState<string>("");
  const set = <K extends keyof Options>(k: K, v: Options[K]) => setOpts({ ...opts, [k]: v });
  const envLLM = health?.llm;

  const onKey = async (v: string) => {
    set("llm_key", v);
    if (v.length < 8) { setDetected(""); return; }
    try {
      const r = await api.checkKey(v);
      setDetected(r.detected?.enabled ? `${r.detected.provider} · ${r.detected.model}` : "Key not recognised. Set LLM_PROVIDER on the server.");
    } catch { setDetected(""); }
  };

  return (
    <section className="stack">
      <h2>Settings</h2>
      <div>
        <div className="seg" role="group" aria-label="Platform">
          {PLATFORMS.map((p) => (
            <button key={p.id} aria-pressed={opts.platform === p.id} onClick={() => set("platform", p.id)} title={p.hint}>{p.label}</button>
          ))}
        </div>
        <p className="hint">Length window: {PLATFORMS.find((p) => p.id === opts.platform)?.hint}</p>
      </div>
      <div className="grid2">
        <label className="field">Promos to return<input type="number" min={1} max={200} value={opts.top_k} onChange={(e) => set("top_k", Number(e.target.value))} /></label>
        <label className="field">Max per episode<input type="number" min={1} max={20} value={opts.max_per_episode} onChange={(e) => set("max_per_episode", Number(e.target.value))} /></label>
      </div>
      <label className="field">Minimum score ({opts.min_score})
        <input type="range" min={0} max={90} step={5} value={opts.min_score} onChange={(e) => set("min_score", Number(e.target.value))} />
      </label>
      <label className="check"><input type="checkbox" checked={opts.enable_montages} onChange={(e) => set("enable_montages", e.target.checked)} /> Allow stitched promos (several moments)</label>
      <label className="field">Show title<input type="text" value={opts.show_title} onChange={(e) => set("show_title", e.target.value)} placeholder="From the file name if empty" /></label>

      <h2 style={{ marginTop: 6 }}>AI judge</h2>
      <label className="check"><input type="checkbox" checked={opts.use_llm} onChange={(e) => set("use_llm", e.target.checked)} /> Re-rank the best candidates with an LLM</label>
      <span className="hint">
        {envLLM?.enabled ? <>Server key: <b>{envLLM.provider}</b> · {envLLM.model}.</> : <>No server key set, so the rules run alone.</>}
        {" "}Paste any one key below (Gemini, Groq, OpenAI, Anthropic, OpenRouter and others). The provider is detected from the key, which is used for this run only and never stored.
      </span>
      <input type="password" autoComplete="off" value={opts.llm_key} onChange={(e) => onKey(e.target.value)} placeholder="LLM API key (optional)" aria-label="LLM API key" />
      {detected && <span className="hint">Detected: {detected}</span>}
    </section>
  );
}
