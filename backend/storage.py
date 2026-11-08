"""In-memory run/job stores + feedback file.

Local/Docker: runs are also written to outputs/runs/<run_id>/ so nothing is lost.
Vercel: the filesystem is read-only except /tmp and instances are short-lived,
so the browser keeps the result and exports are generated statelessly.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("PROMO_READONLY_FS"))
DATA_DIR = Path("/tmp/promo-data") if SERVERLESS else ROOT
RUNS_DIR = DATA_DIR / "outputs" / "runs"
FEEDBACK_FILE = DATA_DIR / "data" / "feedback" / "feedback.jsonl"


class RunStore:
    def __init__(self, capacity: int = 20):
        self._runs: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()
        self.capacity = capacity

    def put(self, run: dict) -> None:
        with self._lock:
            self._runs[run["run_id"]] = run
            self._runs.move_to_end(run["run_id"])
            while len(self._runs) > self.capacity:
                self._runs.popitem(last=False)

    def get(self, run_id: str) -> Optional[dict]:
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            p = RUNS_DIR / run_id / "promos.json"
            if p.exists():
                run = json.loads(p.read_text(encoding="utf-8"))
        return run

    def list(self) -> list[dict]:
        with self._lock:
            return [{"run_id": k, "title": v["show"]["title"], "promos": len(v["promos"]), "created_at": v["created_at"]}
                    for k, v in reversed(self._runs.items())]


class JobStore:
    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        jid = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[jid] = {"id": jid, "status": "queued", "stage": "Queued", "progress": 0.0, "created": time.time()}
        return jid

    def update(self, jid: str, **kw) -> None:
        with self._lock:
            if jid in self._jobs:
                self._jobs[jid].update(kw)

    def get(self, jid: str) -> Optional[dict]:
        with self._lock:
            j = self._jobs.get(jid)
            return dict(j) if j else None

    def gc(self, max_age: float = 3600) -> None:
        now = time.time()
        with self._lock:
            for k in [k for k, v in self._jobs.items() if now - v["created"] > max_age]:
                self._jobs.pop(k, None)


def append_feedback(item: dict) -> int:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    item = {**item, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(item) + "\n")
    return sum(1 for _ in open(FEEDBACK_FILE, encoding="utf-8"))


def read_feedback() -> list[dict]:
    if not FEEDBACK_FILE.exists():
        return []
    return [json.loads(line) for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


runs = RunStore()
jobs = JobStore()
