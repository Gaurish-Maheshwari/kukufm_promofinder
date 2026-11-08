"""Collect every screenplay document from a file, a folder (recursively) or a zip.

- Zips are read in memory (no extraction to disk -> no zip-slip), nested zips
  are followed up to 3 levels, and a size budget guards against zip bombs.
- macOS/Windows junk (__MACOSX, .DS_Store, Thumbs.db, ~$ temp files) is skipped.
- Output is naturally sorted so "Ep 2" comes before "Ep 10".
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from pathlib import Path
from typing import Iterable, Optional, Union

from ..models import SourceDoc
from .extractors import SUPPORTED_EXT, extract, sniff

MAX_TOTAL_BYTES = 300 * 1024 * 1024      # 300 MB uncompressed per run
MAX_ZIP_DEPTH = 3
JUNK_RE = re.compile(r"(^|/)(__MACOSX|\.DS_Store|Thumbs\.db|desktop\.ini|~\$|\.)", re.I)

WORD_NUMS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}


KNOWN_EXT = {".txt", ".md", ".markdown", ".fountain", ".text", ".screenplay", ".rtf", ".script", ".log", ".pdf", ".docx",
             ".doc", ".odt", ".html", ".htm", ".xlsx", ".xls", ".srt", ".vtt", ".csv", ".tsv", ".json", ".zip", ".yaml",
             ".yml", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mov", ".mp3", ".wav", ".pages", ".key", ".numbers"}


MEDIA_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp", ".tif", ".tiff", ".svg", ".mp4", ".mov", ".m4v",
             ".avi", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".psd", ".ai", ".exe", ".dmg",
             ".pages", ".key", ".numbers", ".doc", ".xls", ".ppt", ".pptx", ".7z", ".rar", ".gz", ".tar"}


def _ext(name: str) -> str:
    """Extension only if it is a real one: 'I Married a Broken Soldier. He was a Duke' has none."""
    e = os.path.splitext(name)[1].lower()
    return e if e in KNOWN_EXT or re.fullmatch(r"\.[a-z0-9]{1,5}", e) and not re.search(r"\s", e) else ""


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def episode_from_name(name: str) -> Optional[int]:
    """Guess an episode number from a file name. Returns None if unsure."""
    base = os.path.basename(name)
    stem = base[: -len(_ext(base))] if _ext(base) else base
    s = stem.lower().replace("_", " ").replace("-", " ").replace(".", " ")
    for pat in (r"s\d{1,2}\s*e(\d{1,3})", r"\b(?:episode|ep|epi|e)\s*#?\s*(\d{1,3})\b", r"(?:episode|ep)(\d{1,3})"):
        m = re.search(pat, s)
        if m:
            return int(m.group(1))
    m = re.search(r"\b(?:episode|ep)\s+([a-z]+)\b", s)
    if m and m.group(1) in WORD_NUMS:
        return WORD_NUMS[m.group(1)]
    m = re.fullmatch(r"\s*(\d{1,3})\s*", s)  # "07.txt"
    if m:
        return int(m.group(1))
    nums = re.findall(r"\d{1,3}", s)
    if len(nums) == 1:
        return int(nums[0])
    return None


class _Budget:
    def __init__(self, limit: int = MAX_TOTAL_BYTES):
        self.left = limit

    def take(self, n: int, what: str):
        self.left -= n
        if self.left < 0:
            raise ValueError(f"Input too large (>{MAX_TOTAL_BYTES // (1024 * 1024)} MB uncompressed) at {what}")


REPO_DOC_RE = re.compile(r"^(readme|license|licence|changelog|contributing|notes?_to_self|\.gitkeep|manual_promos.*|my_manual_promos.*)(\.[a-z0-9]+)?$", re.I)


def _is_junk(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    if parts and REPO_DOC_RE.match(parts[-1]):
        return True       # README/LICENSE in the input folder are not episodes; manual promos are loaded separately
    return any(JUNK_RE.search(p) for p in parts if p not in ("", ".", ".."))


def _docs_from_bytes(name: str, rel: str, data: bytes, budget: _Budget, depth: int, warnings: list[str]) -> list[SourceDoc]:
    ext = _ext(name)
    if ext == ".zip" or (ext not in SUPPORTED_EXT and data[:4] == b"PK\x03\x04" and sniff(data) == ".zip"):
        return _docs_from_zip(rel, data, budget, depth + 1, warnings)
    if ext in MEDIA_EXT:
        hint = " (save it as .docx, .pdf or .txt)" if ext in (".doc", ".pages", ".xls", ".ppt", ".pptx", ".key", ".numbers") else ""
        warnings.append(f"Skipped unsupported non-text file: {rel}{hint}")
        return []
    if ext not in SUPPORTED_EXT:
        guess = sniff(data)
        if guess is None or guess not in SUPPORTED_EXT:
            warnings.append(f"Skipped unsupported file: {rel}")
            return []
        warnings.append(f"{rel}: unknown extension, read as {guess} based on its content")
        ext = guess
    try:
        text = extract(ext, data)
    except Exception as exc:  # keep going, report it
        warnings.append(f"Could not read {rel}: {exc}")
        return []
    if not text.strip():
        warnings.append(f"Empty file: {rel}")
        return []
    return [SourceDoc(name=name, path=rel, text=text, kind=ext.lstrip("."), episode_hint=episode_from_name(rel))]


def _docs_from_zip(rel: str, data: bytes, budget: _Budget, depth: int, warnings: list[str]) -> list[SourceDoc]:
    if depth > MAX_ZIP_DEPTH:
        warnings.append(f"Zip nested too deep, skipped: {rel}")
        return []
    docs: list[SourceDoc] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        warnings.append(f"Corrupt zip: {rel}")
        return []
    with zf:
        for info in sorted(zf.infolist(), key=lambda i: natural_key(i.filename)):
            if info.is_dir() or _is_junk(info.filename):
                continue
            budget.take(info.file_size, f"{rel}!/{info.filename}")
            member = zf.read(info)
            docs += _docs_from_bytes(os.path.basename(info.filename), f"{rel}!/{info.filename}", member, budget, depth, warnings)
    return docs


InputLike = Union[str, Path, tuple[str, bytes]]


def load_inputs(inputs: Union[InputLike, Iterable[InputLike]], warnings: Optional[list[str]] = None) -> list[SourceDoc]:
    """Accepts a path (file/folder/zip), a list of paths, or (filename, bytes) tuples (uploads)."""
    warnings = warnings if warnings is not None else []
    budget = _Budget()
    if isinstance(inputs, (str, Path)) or (isinstance(inputs, tuple) and len(inputs) == 2 and isinstance(inputs[1], bytes)):
        inputs = [inputs]  # type: ignore[list-item]
    docs: list[SourceDoc] = []
    for item in inputs:  # type: ignore[union-attr]
        if isinstance(item, tuple):
            name, data = item
            if _is_junk(name):
                continue
            budget.take(len(data), name)
            docs += _docs_from_bytes(os.path.basename(name), name, data, budget, 0, warnings)
            continue
        p = Path(item).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"Input not found: {p}")
        if p.is_file():
            data = p.read_bytes()
            budget.take(len(data), str(p))
            docs += _docs_from_bytes(p.name, p.name, data, budget, 0, warnings)
        else:
            for f in sorted((f for f in p.rglob("*") if f.is_file()), key=lambda f: natural_key(str(f.relative_to(p)))):
                rel = str(f.relative_to(p))
                if _is_junk(rel):
                    continue
                data = f.read_bytes()
                budget.take(len(data), rel)
                docs += _docs_from_bytes(f.name, rel, data, budget, 0, warnings)
    docs.sort(key=lambda d: (d.episode_hint if d.episode_hint is not None else 10**6, natural_key(d.path)))
    return docs
