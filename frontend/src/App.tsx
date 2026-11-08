import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { Health, Options, RunResult } from "./types";
import { store } from "./lib/format";
import { UploadPanel } from "./components/UploadPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { PromoList } from "./components/PromoList";
import { PromoDetail } from "./components/PromoDetail";
import { Heatmap } from "./components/Heatmap";
import { Comparison } from "./components/Comparison";
import { MetricsPanel, QualityPanel } from "./components/MetricsPanel";
import { ExportBar } from "./components/ExportBar";

type Tab = "promos" | "plan" | "map" | "compare" | "quality" | "metrics" | "export";

const DEFAULTS: Options = {
  platform: "any", top_k: 30, min_score: 45, max_per_episode: 3, enable_montages: true, use_llm: true, llm_key: "", show_title: "",
};

function Logo() {
  return (
    <svg width="30" height="40" viewBox="0 0 30 40" aria-hidden="true">
      <rect x="1" y="1" width="28" height="38" rx="6" fill="none" stroke="var(--ink)" strokeWidth="2" />
      <rect x="7" y="9" width="4" height="22" rx="1" fill="var(--hook)" />
      <rect x="19" y="9" width="4" height="22" rx="1" fill="var(--cliff)" />
      <rect x="11" y="18" width="8" height="4" fill="var(--ink-3)" />
    </svg>
  );
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [opts, setOpts] = useState<Options>(() => ({ ...DEFAULTS, ...store.get<Partial<Options>>("pf.opts", {}), llm_key: "" }));
  const [files, setFiles] = useState<File[]>([]);
  const [manual, setManual] = useState<File | null>(null);
  const [serverPath, setServerPath] = useState("data/input");
  const [run, setRun] = useState<RunResult | null>(() => store.get<RunResult | null>("pf.lastRun", null));
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(() => store.get<Tab>("pf.tab", "promos"));
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<{ label: string; frac: number }>({ label: "", frac: 0 });
  const [error, setError] = useState("");

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  useEffect(() => { const { llm_key: _k, ...rest } = opts; store.set("pf.opts", rest); }, [opts]);
  useEffect(() => { store.set("pf.tab", tab); }, [tab]);
  useEffect(() => {
    if (!run) return;
    store.set("pf.lastRun", run);
    if (!selected || !run.promos.find((p) => p.id === selected)) setSelected(run.promos[0]?.id ?? null);
  }, [run]); // eslint-disable-line react-hooks/exhaustive-deps

  const durations = useMemo(() => Object.fromEntries((run?.show.episodes ?? []).map((e) => [e.number, e.duration])), [run]);
  const promo = run?.promos.find((p) => p.id === selected) ?? null;

  const go = async (mode: "files" | "sample" | "server") => {
    setBusy(true); setError(""); setStage({ label: "Starting", frac: 0.02 });
    try {
      let r: RunResult;
      if (mode === "sample") r = await api.sample(opts, true);
      else if (mode === "server") r = await api.serverFolder(serverPath, null, opts);
      else r = await api.analyze(files, manual, opts, (label, frac) => setStage({ label, frac }));
      setRun(r);
      setTab(r.comparison && mode !== "sample" ? "compare" : "promos");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false); setStage({ label: "", frac: 0 });
    }
  };

  const open = (id: string) => { setSelected(id); setTab("promos"); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const canRunFiles = files.length > 0;
  const canRunServer = !canRunFiles && !!health?.local_paths && serverPath.trim().length > 0;
  const llm = run?.settings.llm;

  return (
    <div className="app">
      <aside className="rail">
        <div className="brand">
          <Logo />
          <div><h1>Promo Finder</h1><p>Hook in 3 seconds, cut on a cliffhanger, exact timecodes.</p></div>
        </div>
        <UploadPanel files={files} setFiles={setFiles} manual={manual} setManual={setManual}
          serverPath={serverPath} setServerPath={setServerPath} allowServerPath={!!health?.local_paths} />
        <div className="stack">
          <button className="btn primary" disabled={busy || (!canRunFiles && !canRunServer)} onClick={() => go(canRunFiles ? "files" : "server")}>
            {busy ? "Finding promos" : canRunFiles ? `Find promos in ${files.length} file${files.length > 1 ? "s" : ""}` : canRunServer ? `Find promos in ${serverPath}` : "Add screenplays to start"}
          </button>
          {busy && <div className="progress" aria-label={stage.label}><i style={{ width: `${Math.max(4, stage.frac * 100)}%` }} /></div>}
          {busy && stage.label && <span className="hint">{stage.label}</span>}
          <button className="btn" disabled={busy} onClick={() => go("sample")}>Try the sample show</button>
          {error && <div className="error" role="alert">{error}</div>}
        </div>
        <SettingsPanel opts={opts} setOpts={setOpts} health={health} />
      </aside>

      <main className="main">
        {!run ? (
          <div className="empty">
            <h2>Find the clips that make people stop scrolling.</h2>
            <p>Give it a show’s screenplays. It reads every scene, line and action with its timestamp, then returns
              20–60 second promos that open on a hook and cut on a cliffhanger, ranked, with IN/OUT points your editors can drop straight onto a timeline.</p>
            <ol className="steps">
              <li>Add the episodes on the left: a folder, separate files or a zip.</li>
              <li>Optionally add the promos you picked by hand to see how many the tool also finds.</li>
              <li>Review the ranked list, then export a cut sheet or an EDL.</li>
            </ol>
            <div className="demo"><button className="btn" onClick={() => go("sample")} disabled={busy}>Run the 8-episode sample show</button></div>
          </div>
        ) : (
          <>
            <div className="top">
              <div>
                <h2>{run.show.title}</h2>
                <div className="sub">
                  {run.show.episodes.length} episodes, {run.show.total_minutes} min. {run.promos.length} promos for {run.settings.platform === "any" ? "any platform" : run.settings.platform}.
                  {" "}Ranked by {llm?.enabled ? `rules plus ${llm.provider} (${llm.model})` : "rules only"}.
                </div>
              </div>
              <span className={`pill ${llm?.enabled ? "on" : ""}`}><span className="dot" />{llm?.enabled ? "AI judge on" : "Rules only"}</span>
            </div>
            <nav className="tabs" role="tablist">
              {([
                ["promos", "Ranked promos", run.promos.length],
                ["plan", "Posting order", null],
                ["map", "Show map", null],
                ["compare", "Vs. your picks", run.comparison ? `${run.comparison.summary.matched}/${run.comparison.summary.manual_total}` : null],
                ["quality", "Quality check", Object.values(run.quality.flag_counts).reduce((a, b) => a + b.count, 0) || null],
                ["metrics", "Metrics", null],
                ["export", "Export", null],
              ] as [Tab, string, number | string | null][]).map(([id, label, n]) => (
                <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}{n != null && <span className="count">{n}</span>}</button>
              ))}
            </nav>

            {(tab === "promos" || tab === "plan") && (
              <div className="workspace">
                <div>
                  {tab === "plan" && (
                    <div className="section">
                      <h3>What to post first, and why</h3>
                      <ol className="plan">
                        {run.posting_plan.slice(0, 10).map((p) => (
                          <li key={p.id}><button className="btn ghost sm" onClick={() => setSelected(p.id)}><b>{p.id}</b></button> {p.rationale}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                  <PromoList promos={run.promos} selected={selected} onSelect={setSelected} durations={durations} order={tab === "plan" ? "post" : "rank"} />
                </div>
                {promo && <PromoDetail promo={promo} run={run} />}
              </div>
            )}
            {tab === "map" && (
              <div className="section">
                <h3>Where the drama peaks</h3>
                <p className="muted small">Each row is an episode, each cell five seconds. Promos are the teal bars, and clicking one opens it.</p>
                <Heatmap run={run} onSelect={open} />
              </div>
            )}
            {tab === "compare" && <Comparison run={run} onSelect={open} />}
            {tab === "quality" && <QualityPanel run={run} onSelect={open} />}
            {tab === "metrics" && <MetricsPanel run={run} />}
            {tab === "export" && (
              <div className="section">
                <h3>Take it to the edit</h3>
                <p className="muted small">Every file is built from this run. Timecodes are per episode, which assumes each episode is its own video file.</p>
                <ExportBar run={run} />
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
