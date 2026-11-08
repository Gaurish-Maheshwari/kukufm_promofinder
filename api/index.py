"""Vercel serverless entry point.

vercel.json rewrites every /api/* request here; FastAPI then routes on the
original path. Everything else is served from the static React build.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PROMO_READONLY_FS", "1")

from backend.app import app  # noqa: E402,F401  (Vercel looks for `app`)
