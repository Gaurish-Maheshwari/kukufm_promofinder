"""Content-addressed disk cache for LLM responses.
Re-running the same show with the same model costs zero calls."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional


class LLMCache:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self.enabled = os.access(self.dir, os.W_OK)
        except OSError:
            self.enabled = False

    @staticmethod
    def key(*parts: Any) -> str:
        h = hashlib.sha256()
        for p in parts:
            h.update(str(p).encode("utf-8"))
            h.update(b"\x1f")
        return h.hexdigest()

    def _path(self, key: str) -> Path:
        return self.dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> Optional[dict]:
        if not self.enabled:
            return None
        p = self._path(key)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def set(self, key: str, value: dict) -> None:
        if not self.enabled:
            return
        p = self._path(key)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(value), encoding="utf-8")
        except OSError:
            pass
