"""Load the editor's manual promos in whatever shape they come in.

Supported:
  CSV / TSV  (template: data/manual_promos/manual_promos_TEMPLATE.csv)
      promo_id, segment, episode, start, end, hook, cliffhanger, notes
      -> one row per segment; rows sharing promo_id form a multi-segment promo.
      A single "timestamps" column like "00:41-01:15" also works.
  JSON       [{"id": "M1", "segments": [{"episode": 3, "start": "00:41", "end": "01:15"}], "hook": "..."}]
  XLSX       same columns as CSV (needs openpyxl)
  TXT / MD   free text, one promo per line/bullet, e.g.
      "M1: Ep 3 00:41-01:15 | hook: the slap | cliff: 'who are you?'"
      "Ep 12 [01:05 - 01:40] + Ep 13 [00:00 - 00:10]"
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from ..ingest.extractors import decode_bytes
from ..timecode import TC_TOKEN, parse_timecode


@dataclass
class ManualPromo:
    id: str
    segments: list[tuple[int, float, float]] = field(default_factory=list)
    hook: str = ""
    cliffhanger: str = ""
    notes: str = ""
    rank: Optional[int] = None

    @property
    def duration(self) -> float:
        return sum(max(0.0, e - s) for _, s, e in self.segments)

    def to_dict(self) -> dict:
        return {"id": self.id, "segments": [{"episode": e, "start": s, "end": t} for e, s, t in self.segments],
                "hook": self.hook, "cliffhanger": self.cliffhanger, "notes": self.notes, "rank": self.rank,
                "duration": round(self.duration, 2)}


COLS = {
    "id": ("promo_id", "id", "promo", "promo #", "promo_no", "#", "name"),
    "segment": ("segment", "segment_order", "seg", "part", "order"),
    "episode": ("episode", "ep", "episode_number", "episode no", "ep no"),
    "start": ("start", "in", "start_time", "start_ts", "from", "tc_in"),
    "end": ("end", "out", "end_time", "end_ts", "to", "tc_out"),
    "range": ("timestamps", "timestamp", "range", "time", "tc"),
    "hook": ("hook",),
    "cliffhanger": ("cliffhanger", "cliff", "ending"),
    "notes": ("notes", "why", "comment", "comments", "reason"),
    "rank": ("rank", "priority", "post_order"),
}
RANGE_RE = re.compile(r"(" + TC_TOKEN + r")\s*(?:-->|->|–|—|-|to)\s*(" + TC_TOKEN + r")", re.I)
EP_RE = re.compile(r"\b(?:s\d{1,2}\s*)?(?:episode|ep|e)\s*\.?\s*#?\s*(\d{1,3})\b", re.I)


def _get(row: dict, key: str) -> str:
    norm = {(k or "").strip().lower(): v for k, v in row.items()}
    for alias in COLS[key]:
        if alias in norm and norm[alias] is not None and str(norm[alias]).strip() != "":
            return str(norm[alias]).strip()
    return ""


def _ep_num(s: str) -> Optional[int]:
    m = re.search(r"\d{1,3}", s or "")
    return int(m.group()) if m else None


def _tc(s: str) -> Optional[float]:
    s = (s or "").strip().strip("[]()")
    if not s:
        return None
    v = parse_timecode(s)
    if v is None:
        try:
            return float(s)
        except ValueError:
            return None
    return v


def _from_rows(rows: list[dict], warnings: list[str]) -> list[ManualPromo]:
    promos: dict[str, ManualPromo] = {}
    order: list[str] = []
    for n, row in enumerate(rows, 1):
        if not any(str(v or "").strip() for v in row.values()):
            continue
        first_val = str(next(iter(row.values()), "") or "").strip()
        if first_val.startswith("#"):
            continue  # comment rows in the template
        pid = _get(row, "id") or f"M{n}"
        ep = _ep_num(_get(row, "episode"))
        start, end = _tc(_get(row, "start")), _tc(_get(row, "end"))
        rng = _get(row, "range")
        if (start is None or end is None) and rng:
            m = RANGE_RE.search(rng)
            if m:
                start, end = parse_timecode(m.group(1)), parse_timecode(m.group(2))
            if ep is None:
                em = EP_RE.search(rng)
                ep = int(em.group(1)) if em else None
        if ep is None or start is None or end is None or end <= start:
            warnings.append(f"Manual promo row {n} skipped (need episode, start < end): {dict(row)}")
            continue
        if pid not in promos:
            r = _get(row, "rank")
            promos[pid] = ManualPromo(id=pid, rank=int(r) if r.isdigit() else None)
            order.append(pid)
        p = promos[pid]
        p.segments.append((ep, start, end))
        p.hook = p.hook or _get(row, "hook")
        p.cliffhanger = _get(row, "cliffhanger") or p.cliffhanger
        p.notes = p.notes or _get(row, "notes")
    return [promos[k] for k in order]


def _from_text(text: str, warnings: list[str]) -> list[ManualPromo]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip().lstrip("-*•").strip()
        if not s or s.startswith("#"):
            continue
        segs = []
        last_ep = None
        for m in re.finditer(EP_RE.pattern + r"|" + RANGE_RE.pattern, s, re.I):
            if m.group(1):
                last_ep = int(m.group(1))
            elif m.group(2) and last_ep is not None:
                a, b = parse_timecode(m.group(2)), parse_timecode(m.group(3))
                if a is not None and b is not None and b > a:
                    segs.append((last_ep, a, b))
        if not segs:
            continue
        idm = re.match(r"^\s*([A-Za-z]*\d+|[A-Za-z]+\d*)\s*[:.)]", s)
        hook = re.search(r"hook\s*[:=]\s*([^|;]+)", s, re.I)
        cliff = re.search(r"cliff(?:hanger)?\s*[:=]\s*([^|;]+)", s, re.I)
        out.append(ManualPromo(id=idm.group(1) if idm and not EP_RE.match(idm.group(0)) else f"M{len(out) + 1}",
                               segments=segs, hook=hook.group(1).strip() if hook else "",
                               cliffhanger=cliff.group(1).strip() if cliff else ""))
    if not out:
        warnings.append("No promos recognised in the manual text file. Expected lines like 'Ep 3 00:41-01:15'.")
    return out


def load_manual(src: Union[str, Path, tuple[str, bytes]], warnings: Optional[list[str]] = None) -> list[ManualPromo]:
    warnings = warnings if warnings is not None else []
    if isinstance(src, tuple):
        name, data = src
    else:
        p = Path(src)
        name, data = p.name, p.read_bytes()
    ext = os.path.splitext(name)[1].lower()
    if ext in (".csv", ".tsv"):
        text = decode_bytes(data)
        delim = "\t" if ext == ".tsv" or text.count("\t") > text.count(",") else ","
        rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
        return _from_rows(rows, warnings)
    if ext == ".json":
        obj = json.loads(decode_bytes(data))
        items = obj if isinstance(obj, list) else obj.get("promos", [])
        rows = []
        for i, it in enumerate(items, 1):
            segs = it.get("segments") or [it]
            for k, sg in enumerate(segs, 1):
                rows.append({"promo_id": str(it.get("id") or it.get("promo_id") or f"M{i}"), "segment": k,
                             "episode": str(sg.get("episode", it.get("episode", ""))), "start": str(sg.get("start", "")),
                             "end": str(sg.get("end", "")), "hook": it.get("hook", ""), "cliffhanger": it.get("cliffhanger", ""),
                             "notes": it.get("notes", it.get("why", "")), "rank": str(it.get("rank", ""))})
        return _from_rows(rows, warnings)
    if ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            warnings.append("openpyxl not installed; save the sheet as CSV instead.")
            return []
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header = [str(h or "").strip() for h in next(it)]
        rows = [{header[i]: ("" if v is None else str(v)) for i, v in enumerate(r) if i < len(header)} for r in it]
        return _from_rows(rows, warnings)
    return _from_text(decode_bytes(data), warnings)
