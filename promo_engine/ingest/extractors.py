"""Turn bytes of one file into plain text. One function per format.

Everything returns text with one screenplay line per line. Formats:
txt/md/fountain (any common encoding), pdf (pypdf, pdfplumber fallback),
docx (python-docx, including tables), srt/vtt (subtitle cues -> "[start - end] text"),
csv/tsv (columns like time/speaker/text), json (list of beats).
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Callable, Optional

TEXT_EXT = {".txt", ".md", ".markdown", ".fountain", ".text", ".screenplay", ".rtf", ".script", ".log", ".yaml", ".yml"}
SUPPORTED_EXT = TEXT_EXT | {".pdf", ".docx", ".odt", ".html", ".htm", ".xlsx", ".srt", ".vtt", ".csv", ".tsv", ".json"}


def decode_bytes(data: bytes) -> str:
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_txt(data: bytes) -> str:
    text = decode_bytes(data)
    if text.lstrip().startswith("{\\rtf"):
        text = _strip_rtf(text)
    return text


def _strip_rtf(text: str) -> str:
    text = re.sub(r"\\par[d]?", "\n", text)
    text = re.sub(r"\{\\\*[^{}]*\}", "", text)
    text = re.sub(r"\\[a-z]+-?\d* ?", "", text)
    return text.replace("{", "").replace("}", "")


def extract_pdf(data: bytes) -> str:
    text = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
        text = "\n".join(pages)
    except Exception:  # pragma: no cover - fallback path
        text = ""
    if len(text.strip()) < 20:
        try:
            import pdfplumber  # optional, better layout on some PDFs
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception:
            pass
    if len(text.strip()) < 20:
        raise ValueError("PDF has no extractable text (scanned image?). OCR it first, e.g. `ocrmypdf in.pdf out.pdf`.")
    return _clean_pdf_text(text)


def _clean_pdf_text(text: str) -> str:
    lines = text.splitlines()
    # drop page furniture: "Page 3 of 12", lone page numbers
    out = []
    for ln in lines:
        s = ln.strip()
        if re.fullmatch(r"(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\.?", s, re.I):
            continue
        out.append(ln)
    # drop running headers/footers: identical short lines repeated on many pages
    counts: dict[str, int] = {}
    for ln in out:
        s = ln.strip()
        if 0 < len(s) < 80:
            counts[s] = counts.get(s, 0) + 1
    def furniture(s: str, c: int) -> bool:
        if re.search(r"\d:\d\d", s) or re.match(r"^(ep|episode|scene|int\.|ext\.)", s, re.I):
            return False
        if c >= 3:
            return True
        # running headers/footers that appear on 2+ pages: "SHOW — CONFIDENTIAL DRAFT", "© Kuku 2026"
        return c >= 2 and (bool(re.search(r"confidential|draft|all rights reserved|copyright|©|www\.|\.com", s, re.I))
                           or (len(s.split()) >= 3 and s.upper() == s))
    repeated = {s for s, c in counts.items() if furniture(s, c)}
    return "\n".join(ln for ln in out if ln.strip() not in repeated)


def extract_docx(data: bytes) -> str:
    import docx  # python-docx
    d = docx.Document(io.BytesIO(data))
    lines = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_subtitles(data: bytes) -> str:
    """SRT/VTT cues become '[00:00:01.000 - 00:00:03.500] text' lines."""
    text = decode_bytes(data)
    out = []
    blocks = re.split(r"\n\s*\n", text.replace("\r", ""))
    for b in blocks:
        m = re.search(r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})", b)
        if not m:
            continue
        rest = b[m.end():].strip().replace("\n", " ")
        rest = re.sub(r"<[^>]+>", "", rest)
        if rest:
            out.append(f"[{m.group(1)} - {m.group(2)}] {rest}")
    return "\n".join(out)


_TIME_COLS = ("timestamp", "time", "start", "tc", "timecode", "in", "start_time")
_END_COLS = ("end", "out", "end_time", "stop")
_SPK_COLS = ("speaker", "character", "who", "name")
_TXT_COLS = ("text", "line", "dialogue", "content", "description", "action")
_TYPE_COLS = ("type", "kind", "beat_type", "element")
_EP_COLS = ("episode", "ep", "episode_number")


def _pick(row: dict, keys) -> str:
    for k in keys:
        for rk in row:
            if rk and rk.strip().lower() == k:
                return (row[rk] or "").strip()
    return ""


def extract_table(data: bytes, delimiter: str | None = None) -> str:
    text = decode_bytes(data)
    if delimiter is None:
        delimiter = "\t" if text.count("\t") > text.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    out, last_ep = [], None
    for row in reader:
        ep = _pick(row, _EP_COLS)
        if ep and ep != last_ep:
            out.append(f"EPISODE {re.sub(r'[^0-9]', '', ep) or ep}")
            last_ep = ep
        start, end = _pick(row, _TIME_COLS), _pick(row, _END_COLS)
        spk, txt, typ = _pick(row, _SPK_COLS), _pick(row, _TXT_COLS), _pick(row, _TYPE_COLS).upper()
        if not txt:
            continue
        tc = f"[{start} - {end}]" if start and end else (f"[{start}]" if start else "")
        if typ.startswith("SCENE"):
            out.append(f"{tc} SCENE: {txt}")
        elif spk and typ not in ("ACTION", "DESCRIPTION"):
            out.append(f"{tc} {spk.upper()}: {txt}")
        else:
            out.append(f"{tc} ACTION: {txt}")
    return "\n".join(out)


def extract_json(data: bytes) -> str:
    obj = json.loads(decode_bytes(data))
    rows = obj if isinstance(obj, list) else obj.get("beats") or obj.get("lines") or obj.get("scenes") or []
    buf = io.StringIO()
    if rows and isinstance(rows[0], dict):
        keys = sorted({k for r in rows for k in r})
        w = csv.DictWriter(buf, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (v if not isinstance(v, (dict, list)) else json.dumps(v)) for k, v in r.items()})
        return extract_table(buf.getvalue().encode("utf-8"), ",")
    return "\n".join(str(r) for r in rows)


def extract_html(data: bytes) -> str:
    import html as _html
    text = decode_bytes(data)
    text = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<\s*(br|/p|/div|/li|/tr|/h[1-6]|/td)\s*/?>", "\n", text)
    text = re.sub(r"(?i)<\s*td[^>]*>", " | ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return _html.unescape(text)


def extract_odt(data: bytes) -> str:
    import zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("content.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"<text:line-break/>", "\n", xml)
    xml = re.sub(r"</text:(p|h)>", "\n", xml)
    xml = re.sub(r"<text:tab/>", "\t", xml)
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", "", xml))


def extract_xlsx(data: bytes) -> str:
    try:
        import openpyxl
    except ImportError as exc:
        raise ValueError("reading .xlsx needs openpyxl (pip install openpyxl) — or save the sheet as CSV") from exc
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows = []
    for ws in wb.worksheets:
        for r in ws.iter_rows(values_only=True):
            if any(v is not None and str(v).strip() for v in r):
                rows.append(",".join('"' + str("" if v is None else v).replace('"', '""') + '"' for v in r))
    csv_text = "\n".join(rows)
    as_table = extract_table(csv_text.encode("utf-8"), ",")
    # a sheet with recognisable columns becomes beats; otherwise keep the raw cells as lines
    return as_table if as_table.strip() else csv_text.replace('","', " | ").strip('"')


def sniff(data: bytes) -> Optional[str]:
    """Guess a file type from its bytes (for missing/wrong extensions)."""
    head = data[:8]
    if head.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"ID3", b"OggS", b"fLaC", b"RIFF", b"\x1aE\xdf\xa3")) \
            or head[4:8] in (b"ftyp", b"moov"):
        return None                              # images / audio / video
    if head.startswith(b"%PDF"):
        return ".pdf"
    if head.startswith(b"PK\x03\x04"):
        sample = data[:4096] + data[-65536:]
        if b"word/" in sample:
            return ".docx"
        if b"content.xml" in sample and b"opendocument" in data[:400]:
            return ".odt"
        if b"xl/" in sample:
            return ".xlsx"
        return ".zip"
    if head.startswith(b"{\\rtf"):
        return ".rtf"
    txt = data[:4000]
    if b"\x00" in txt and not (txt.startswith(b"\xff\xfe") or txt.startswith(b"\xfe\xff")):
        return None                              # binary we do not understand
    s = decode_bytes(txt).lstrip()
    if s.startswith("<") and re.search(r"(?i)<(html|body|p|div)\b", s):
        return ".html"
    if s[:1] in "[{" and s.rstrip()[-1:] in "]}" :
        return ".json"
    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in s) / max(1, len(s))
    return ".txt" if printable > 0.9 else None


EXTRACTORS: dict[str, Callable[[bytes], str]] = {
    **{ext: extract_txt for ext in TEXT_EXT},
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".odt": extract_odt,
    ".html": extract_html,
    ".htm": extract_html,
    ".xlsx": extract_xlsx,
    ".srt": extract_subtitles,
    ".vtt": extract_subtitles,
    ".csv": lambda b: extract_table(b, ","),
    ".tsv": lambda b: extract_table(b, "\t"),
    ".json": extract_json,
}


def extract(ext: str, data: bytes) -> str:
    """Extract text with the reader for `ext`; if that fails or the extension is wrong,
    retry with the type sniffed from the bytes, then as plain text."""
    ext = ext.lower()
    fn = EXTRACTORS.get(ext)
    errors = []
    if fn is not None:
        try:
            out = fn(data)
            if out and out.strip():
                return out
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ext}: {exc}")
    guess = sniff(data)
    if guess and guess != ext and guess in EXTRACTORS:
        try:
            out = EXTRACTORS[guess](data)
            if out and out.strip():
                return out
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{guess}: {exc}")
    if errors:
        raise ValueError("; ".join(errors))
    if fn is None and guess is None:
        raise ValueError(f"Unsupported or binary file type: {ext or '(no extension)'}")
    return ""
