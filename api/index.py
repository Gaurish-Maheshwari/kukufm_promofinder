"""Vercel serverless entry point.

vercel.json rewrites every /api/* request here; FastAPI then routes on the
original path. Everything else is served from the static React build.

Vercel only treats this file as a function when it can see a top-level
`app` variable, so `app` is assigned at module level below.

Guardrail: if the real backend fails to import (missing file, bad dependency,
wrong Python), a tiny fallback app answers instead of a blank
500 FUNCTION_INVOCATION_FAILED, and /api/health shows the actual error.
"""
import os
import sys
import traceback
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PROMO_READONLY_FS", "1")


def _fallback_app(err: str) -> FastAPI:
    print(err, file=sys.stderr)  # shows up in Vercel's runtime logs
    fb = FastAPI(title="Kuku Promo Finder (startup failed)")

    @fb.api_route("/{path:path}", methods=["GET", "POST"])
    def _startup_failed(path: str = ""):
        return JSONResponse(status_code=500, content={
            "ok": False, "error": "backend failed to start", "python": sys.version.split()[0],
            "files_present": sorted(p.name for p in ROOT.iterdir()), "traceback": err.splitlines()[-12:]})

    return fb


def _load_app() -> FastAPI:
    try:
        from backend.app import app as real_app
        return real_app
    except Exception:  # noqa: BLE001
        return _fallback_app(traceback.format_exc())


app = _load_app()
