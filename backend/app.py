"""FastAPI backend for Kuku Promo Finder.

Local:   uvicorn backend.app:app --reload        (or `make dev`)
Docker:  serves the built React app at / and the API at /api
Vercel:  api/index.py imports `app`; the React build is served as static files
"""
from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from promo_engine import __version__  # noqa: E402
from promo_engine.cli import _load_env  # noqa: E402
from promo_engine.config import load_config  # noqa: E402
from promo_engine.export import (comparison_csv, cut_sheet_csv, edl_all, ffmpeg_script, html_report,  # noqa: E402
                                 markdown_report, markers_csv, promos_csv, save_outputs, to_json)
from promo_engine.llm import build_client, resolve_settings  # noqa: E402
from promo_engine.pipeline import run_pipeline  # noqa: E402

from .schemas import AnalyzeOptions, Feedback, KeyCheck, PathRequest, SampleRequest  # noqa: E402
from .storage import RUNS_DIR, SERVERLESS, append_feedback, jobs, read_feedback, runs  # noqa: E402

_load_env()
MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", "4" if SERVERLESS else "200"))
ALLOW_LOCAL_PATHS = os.environ.get("ALLOW_LOCAL_PATHS", "0" if SERVERLESS else "1") == "1"
INPUT_ROOT = Path(os.environ.get("INPUT_ROOT", ROOT / "data")).resolve()
SAMPLE_ZIP = ROOT / "data" / "sample" / "sample_show.zip"
SAMPLE_MANUAL = ROOT / "data" / "sample" / "manual_promos_sample.csv"

app = FastAPI(title="Kuku Promo Finder API", version=__version__,
              description="Find ready-to-cut promos (hook → cliffhanger) in microdrama screenplays.")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])

EXPORTS = {
    "json": ("promos.json", "application/json", to_json),
    "csv": ("promos.csv", "text/csv", promos_csv),
    "cutsheet": ("editor_cut_sheet.csv", "text/csv", cut_sheet_csv),
    "md": ("promos_report.md", "text/markdown", markdown_report),
    "html": ("report.html", "text/html", html_report),
    "edl": ("promos.edl", "text/plain", edl_all),
    "markers": ("markers.csv", "text/csv", markers_csv),
    "ffmpeg": ("ffmpeg_cuts.sh", "text/x-shellscript", ffmpeg_script),
    "comparison": ("comparison_vs_manual.csv", "text/csv", comparison_csv),
}


# ------------------------------------------------------------------ helpers
def _run(inputs, manual, opts: AnalyzeOptions, progress=None) -> dict:
    res = run_pipeline(inputs, platform=opts.platform, top_k=opts.top_k, manual=manual, use_llm=opts.use_llm,
                       llm_key=opts.llm_key or None, llm_model=opts.llm_model or None, show_title=opts.show_title,
                       progress=progress, overrides=opts.overrides())
    run = res.to_dict(include_beats=opts.include_timeline)
    runs.put(run)
    if not SERVERLESS:
        try:
            save_outputs(run, RUNS_DIR / run["run_id"], res.cfg)
        except OSError:
            pass
    return run


async def _read_uploads(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    out, total = [], 0
    for f in files:
        data = await f.read()
        total += len(data)
        if total > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"Upload larger than {MAX_UPLOAD_MB:.0f} MB. Zip the folder or run locally/Docker.")
        out.append((f.filename or "upload.txt", data))
    return out


def _parse_options(options: Optional[str]) -> AnalyzeOptions:
    try:
        return AnalyzeOptions(**(json.loads(options) if options else {}))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"Bad options: {exc}")


def _safe_path(p: str) -> Path:
    path = (ROOT / p).resolve() if not os.path.isabs(p) else Path(p).resolve()
    if not ALLOW_LOCAL_PATHS:
        raise HTTPException(403, "Reading server folders is disabled here. Upload files instead.")
    if INPUT_ROOT not in path.parents and path != INPUT_ROOT:
        raise HTTPException(403, f"Only folders inside {INPUT_ROOT} can be read.")
    if not path.exists():
        raise HTTPException(404, f"Not found: {p}")
    return path


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return HTTPException(422, str(exc))
    traceback.print_exc()
    return HTTPException(500, f"{type(exc).__name__}: {exc}")


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__, "serverless": SERVERLESS, "local_paths": ALLOW_LOCAL_PATHS,
            "max_upload_mb": MAX_UPLOAD_MB, "llm": resolve_settings().describe()}


@app.get("/api/options")
def options():
    cfg = load_config()
    return {"platforms": cfg["platforms"], "promo": cfg["promo"], "weights": cfg["weights"],
            "weights_source": cfg.get("_weights_source"), "input_root": str(INPUT_ROOT.relative_to(ROOT)) if INPUT_ROOT.is_relative_to(ROOT) else str(INPUT_ROOT)}


@app.post("/api/llm/check")
def llm_check(body: KeyCheck = Body(default=KeyCheck())):
    s = resolve_settings(key=body.key)
    out = {"detected": s.describe()}
    if body.ping and s.enabled:
        try:
            client = build_client(load_config(), key=body.key)
            out["model"] = client.model
            out["ping"] = client.ping()
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc)[:300]
    return out


@app.post("/api/analyze")
async def analyze(files: list[UploadFile] = File(...), manual: Optional[UploadFile] = File(None),
                  options: Optional[str] = Form(None)):
    opts = _parse_options(options)
    try:
        inputs = await _read_uploads(files)
        man = (manual.filename or "manual.csv", await manual.read()) if manual is not None else None
        return JSONResponse(_run(inputs, man, opts))
    except Exception as exc:  # noqa: BLE001
        raise _error(exc)


@app.post("/api/jobs")
async def create_job(files: list[UploadFile] = File(...), manual: Optional[UploadFile] = File(None),
                     options: Optional[str] = Form(None)):
    """Background job with progress (local/Docker). On Vercel it completes inside the request."""
    opts = _parse_options(options)
    inputs = await _read_uploads(files)
    man = (manual.filename or "manual.csv", await manual.read()) if manual is not None else None
    jid = jobs.create()

    def work():
        try:
            run = _run(inputs, man, opts, progress=lambda stage, frac: jobs.update(jid, stage=stage, progress=frac, status="running"))
            jobs.update(jid, status="done", progress=1.0, stage="Done", run_id=run["run_id"])
        except Exception as exc:  # noqa: BLE001
            jobs.update(jid, status="error", error=str(_error(exc).detail))

    if SERVERLESS:
        work()
        job = jobs.get(jid)
        if job and job.get("run_id"):
            job["result"] = runs.get(job["run_id"])
        return job
    threading.Thread(target=work, daemon=True).start()
    jobs.gc()
    return jobs.get(jid)


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    job = jobs.get(jid)
    if not job:
        raise HTTPException(404, "Unknown job")
    if job.get("status") == "done":
        job["result"] = runs.get(job["run_id"])
    return job


@app.post("/api/analyze/sample")
def analyze_sample(body: SampleRequest = Body(default=SampleRequest())):
    if not SAMPLE_ZIP.exists():
        raise HTTPException(404, "Sample data missing — run `python scripts/make_sample_data.py`.")
    opts = body.options
    if not opts.show_title:
        opts.show_title = "The Maid Who Owns the Mansion (sample)"
    try:
        return _run(SAMPLE_ZIP, SAMPLE_MANUAL if body.with_manual else None, opts)
    except Exception as exc:  # noqa: BLE001
        raise _error(exc)


@app.post("/api/analyze/path")
def analyze_path(body: PathRequest):
    """Read a folder/zip that already lives on the server (local or Docker volume), e.g. data/input."""
    path = _safe_path(body.path)
    manual = _safe_path(body.manual_path) if body.manual_path else None
    try:
        return _run(path, manual, body.options)
    except Exception as exc:  # noqa: BLE001
        raise _error(exc)


@app.get("/api/runs")
def list_runs():
    return runs.list()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found (serverless instances forget runs — re-run or use the stateless export).")
    return run


def _export(run: dict, fmt: str) -> Response:
    if fmt not in EXPORTS:
        raise HTTPException(404, f"Unknown format. Choose: {', '.join(EXPORTS)}")
    name, mime, fn = EXPORTS[fmt]
    import re
    base = re.sub(r"[^a-z0-9]+", "_", (run.get("show", {}).get("title") or "promos").lower()).strip("_")[:40]
    return Response(content=fn(run), media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{base}_{name}"'})


@app.get("/api/runs/{run_id}/export/{fmt}")
def export_run(run_id: str, fmt: str):
    run = runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return _export(run, fmt)


@app.post("/api/export/{fmt}")
def export_stateless(fmt: str, run: dict = Body(...)):
    """Stateless: the browser posts the run it already has (works on serverless)."""
    if "promos" not in run or "show" not in run:
        raise HTTPException(422, "Body must be a run result")
    return _export(run, fmt)


@app.post("/api/feedback")
def feedback(item: Feedback):
    try:
        n = append_feedback(item.model_dump())
    except OSError as exc:
        raise HTTPException(500, f"Could not store feedback: {exc}")
    return {"ok": True, "stored": n, "note": "Run `promo-finder learn` to fold feedback into the weights."}


@app.get("/api/feedback")
def list_feedback():
    return read_feedback()


@app.get("/api/sample/manual", response_class=PlainTextResponse)
def sample_manual():
    return SAMPLE_MANUAL.read_text(encoding="utf-8") if SAMPLE_MANUAL.exists() else ""


@app.get("/api/template/manual", response_class=PlainTextResponse)
def manual_template():
    p = ROOT / "data" / "manual_promos" / "manual_promos_TEMPLATE.csv"
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ------------------------------------------------------------------ static frontend (Docker / local prod)
DIST = ROOT / "frontend" / "dist"
if DIST.exists() and not SERVERLESS:
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        f = DIST / full_path
        if full_path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
