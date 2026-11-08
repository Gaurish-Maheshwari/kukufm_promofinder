"""Vercel serverless entry point.

vercel.json rewrites every /api/* request here; FastAPI then routes on the
original path. Everything else is served from the static React build.

Guardrail: if the real app fails to import on Vercel (missing file, bad
dependency, wrong Python), a tiny fallback app answers instead of a blank
500 FUNCTION_INVOCATION_FAILED, and /api/health shows the actual error.
"""
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PROMO_READONLY_FS", "1")

try:
    from backend.app import app  # noqa: E402,F401  (Vercel looks for `app`)
except Exception:  # noqa: BLE001
    _ERR = traceback.format_exc()
    print(_ERR, file=sys.stderr)          # shows up in Vercel's runtime logs
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Kuku Promo Finder (startup failed)")

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    def _startup_failed(path: str = ""):
        return JSONResponse(status_code=500, content={
            "ok": False, "error": "backend failed to start", "python": sys.version.split()[0],
            "files_present": sorted(p.name for p in ROOT.iterdir()), "traceback": _ERR.splitlines()[-12:]})
