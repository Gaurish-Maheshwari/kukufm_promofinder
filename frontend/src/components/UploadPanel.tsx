import { useRef, useState } from "react";

const ACCEPT = ".txt,.md,.pdf,.docx,.odt,.html,.htm,.rtf,.srt,.vtt,.csv,.tsv,.xlsx,.json,.fountain,.zip";

interface Props {
  files: File[]; setFiles: (f: File[]) => void;
  manual: File | null; setManual: (f: File | null) => void;
  serverPath: string; setServerPath: (s: string) => void; allowServerPath: boolean;
}

export function UploadPanel({ files, setFiles, manual, setManual, serverPath, setServerPath, allowServerPath }: Props) {
  const [over, setOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const dirRef = useRef<HTMLInputElement>(null);
  const manRef = useRef<HTMLInputElement>(null);

  const add = (list: FileList | null) => {
    if (!list) return;
    const incoming = Array.from(list).filter((f) => !f.name.startsWith(".") && !f.name.startsWith("~$"));
    const key = (f: File) => ((f as any).webkitRelativePath || f.name) + f.size;
    const seen = new Set(files.map(key));
    setFiles([...files, ...incoming.filter((f) => !seen.has(key(f)))]);
  };

  return (
    <section className="stack">
      <h2>Screenplays</h2>
      <div
        className={`drop ${over ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files); }}
      >
        <strong>Drop episodes, a folder’s files or a .zip</strong>
        <span className="small muted">txt · pdf · docx · odt · html · md · srt · csv · xlsx · zip (nested is fine)</span>
        <div className="row">
          <button className="btn sm" onClick={() => fileRef.current?.click()}>Choose files</button>
          <button className="btn sm" onClick={() => dirRef.current?.click()}>Choose folder</button>
        </div>
        <input ref={fileRef} type="file" multiple accept={ACCEPT} hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        <input ref={dirRef} type="file" hidden multiple {...({ webkitdirectory: "", directory: "" } as any)} onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      </div>
      {files.length > 0 && (
        <>
          <ul className="filelist">
            {files.map((f, i) => (
              <li key={i}><span>{(f as any).webkitRelativePath || f.name}</span><span className="mono">{(f.size / 1024).toFixed(0)} KB</span></li>
            ))}
          </ul>
          <button className="btn ghost sm" onClick={() => setFiles([])}>Clear {files.length} file{files.length > 1 ? "s" : ""}</button>
        </>
      )}
      {allowServerPath && (
        <label className="field">
          Or read a folder on the server
          <input type="text" value={serverPath} onChange={(e) => setServerPath(e.target.value)} placeholder="data/input" />
          <span className="hint">Used when no files are chosen above. Put the input pack in <span className="mono">data/input</span>.</span>
        </label>
      )}

      <h2 style={{ marginTop: 6 }}>Your manual promos <span className="muted small">(optional)</span></h2>
      <div className="row">
        <button className="btn sm" onClick={() => manRef.current?.click()}>{manual ? "Replace file" : "Add CSV / sheet / notes"}</button>
        {manual && <button className="btn ghost sm" onClick={() => setManual(null)}>Remove</button>}
        <a className="small" href="/api/template/manual" download="manual_promos_TEMPLATE.csv">Template</a>
      </div>
      {manual && <span className="small mono">{manual.name}</span>}
      <span className="hint">The tool lines your picks up against its own and tells you how many it found.</span>
      <input ref={manRef} type="file" accept=".csv,.tsv,.json,.xlsx,.txt,.md" hidden onChange={(e) => { setManual(e.target.files?.[0] ?? null); e.target.value = ""; }} />
    </section>
  );
}
