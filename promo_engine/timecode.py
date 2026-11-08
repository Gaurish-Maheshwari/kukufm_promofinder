"""Timecode parsing and formatting.

Accepted inputs (all return seconds as float):
    "12"            -> 12.0 (bare seconds, only via parse_timecode)
    "0:12", "00:12" -> 12.0
    "1:02:03"       -> 3723.0
    "00:01:23,456"  -> 83.456  (SRT)    "00:01:23.456" -> 83.456 (VTT)
    "00:00:05:12"   -> 5.4     (SMPTE frames at fps=30)
    "1m23s", "83s", "1m 23.5s"
"""
from __future__ import annotations

import re
from typing import Optional

# One timecode token. Order matters: longest forms first.
TC_TOKEN = (
    r"(?:\d{1,2}:\d{2}:\d{2}[:;]\d{2}"          # SMPTE hh:mm:ss:ff
    r"|\d{1,2}:\d{2}:\d{2}(?:[.,]\d{1,3})?"     # hh:mm:ss(.ms)
    r"|\d{1,3}:\d{2}(?:[.,]\d{1,3})?"           # mm:ss(.ms)
    r"|\d+m\s?\d{1,2}(?:\.\d+)?s"               # 1m23s
    r"|\d+(?:\.\d+)?s(?![a-z])"                 # 83s
    r")"
)
TC_RE = re.compile(TC_TOKEN)
RANGE_SEP = r"\s*(?:-->|->|–|—|-|to|~|/)\s*"

# Timestamp(s) at the start of a line, optionally bracketed, optionally a range,
# followed by an optional separator ("|", ":", "-", tab).
# Separator between the two timecodes of a range: "-", "to", "-->", "|", or a keyword
# ("00:01 | End: 00:04", "Start: 00:01 End: 00:04").
_RANGE_SEP2 = (r"(?:\s*(?:[|,;]|-->|->|–|—|-|~|/)?\s*(?:END|TO|OUT|UNTIL|THRU|THROUGH|STOP)\s*[:=]?\s*"
               r"|" + RANGE_SEP + r"|\s*[|,;]\s*)")
LEADING_TC_RE = re.compile(
    r"^\s*(?:(?:TC|TIME|TIMESTAMP|TIMECODE|TIMING|START|STARTS|FROM|BEGIN|IN|T)\s*[:=]?\s*)?"
    r"[\[\(\{<]?\s*(?P<start>" + TC_TOKEN + r")\s*[\]\)\}>]?"
    r"(?:" + _RANGE_SEP2 + r"[\[\(\{<]?\s*(?P<end>" + TC_TOKEN + r")\s*[\]\)\}>]?)?"
    r"\s*(?:[|:\-–—\t>]\s*)?",
    re.IGNORECASE,
)

# Timestamp(s) at the end of a line in brackets, e.g. "INT. HALL - NIGHT [00:12 - 00:40]"
TRAILING_TC_RE = re.compile(
    r"[\[\(\{]\s*(?P<start>" + TC_TOKEN + r")\s*(?:" + RANGE_SEP + r"(?P<end>" + TC_TOKEN + r"))?\s*[\]\)\}]\s*$",
    re.IGNORECASE,
)


# "Start: (00:01.00) | End: (00:04.80)" or "from 00:01 to 00:04" anywhere in a line
TIMING_PHRASE_RE = re.compile(
    r"(?<!SCENE )(?<!SCENE_)\b(?:START|STARTS|FROM|BEGIN|IN|TC\s*IN)\s*[:=]\s*[\[\(\{]?\s*(?P<start>" + TC_TOKEN + r")\s*[\]\)\}]?"
    r"(?:\s*[|,;/–—-]?\s*(?:END|ENDS|TO|UNTIL|STOP|OUT|TC\s*OUT)\s*[:=]?\s*[\[\(\{]?\s*(?P<end>" + TC_TOKEN + r")\s*[\]\)\}]?)?",
    re.IGNORECASE,
)


def parse_timecode(token: str, fps: float = 30.0) -> Optional[float]:
    """Convert one timecode token to seconds. Returns None when it is not a timecode."""
    if token is None:
        return None
    t = token.strip().lower().replace(" ", "")
    if not t:
        return None
    m = re.fullmatch(r"(\d+)m(\d{1,2}(?:\.\d+)?)s", t)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.fullmatch(r"(\d+(?:\.\d+)?)s?", t)
    if m:
        return float(m.group(1))
    m = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})[:;](\d{2})", t)
    if m:
        h, mi, s, f = (int(x) for x in m.groups())
        return h * 3600 + mi * 60 + s + f / fps
    m = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d{1,3}))?", t)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ms = _frac(m.group(4))
        return h * 3600 + mi * 60 + s + ms
    m = re.fullmatch(r"(\d{1,3}):(\d{2})(?:[.,](\d{1,3}))?", t)
    if m:
        mi, s = int(m.group(1)), int(m.group(2))
        return mi * 60 + s + _frac(m.group(3))
    return None


def _frac(g: Optional[str]) -> float:
    if not g:
        return 0.0
    return int(g) / (10 ** len(g))


def fmt(seconds: float, style: str = "mmss") -> str:
    """Format seconds.

    style: "mmss"  -> 01:23.4   (editor-friendly, tenths)
           "hms"   -> 00:01:23.400
           "smpte" -> 00:01:23:12 (30 fps)
           "srt"   -> 00:01:23,400
    """
    if seconds is None:
        return ""
    seconds = max(0.0, float(seconds))
    if style == "mmss":
        m, s = divmod(seconds, 60)
        return f"{int(m):02d}:{s:04.1f}"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if style == "hms":
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"
    if style == "srt":
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)) % 1000:03d}"
    if style == "smpte":
        return smpte(seconds)
    raise ValueError(f"unknown style {style}")


def smpte(seconds: float, fps: int = 30) -> str:
    total_frames = int(round(max(0.0, seconds) * fps))
    f = total_frames % fps
    s_total = total_frames // fps
    h, rem = divmod(s_total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def split_leading_timecode(line: str, fps: float = 30.0):
    """Return (start, end, rest_of_line). start/end are None if the line has no leading TC.

    Bare integers ("12 Ava walks in") are NOT treated as timecodes — only tokens
    with a colon or an s/m suffix — to avoid eating numbered lists.
    """
    m = LEADING_TC_RE.match(line)
    if m:
        start_tok = m.group("start")
        if ":" in start_tok or re.search(r"\d[ms]", start_tok, re.I):
            start = parse_timecode(start_tok, fps)
            end = parse_timecode(m.group("end"), fps) if m.group("end") else None
            if start is not None:
                return start, end, line[m.end():].strip()
    m = TIMING_PHRASE_RE.search(line)
    if m:          # "AVA (Cold): Start: (00:01.00) | End: (00:02.00) Hello" — a labelled range anywhere in the line
        start = parse_timecode(m.group("start"), fps)
        end = parse_timecode(m.group("end"), fps) if m.group("end") else None
        if start is not None:
            rest = (line[: m.start()] + " " + line[m.end():]).strip(" |\t")
            return start, end, re.sub(r"\s{2,}", " ", rest).strip()
    m = TRAILING_TC_RE.search(line)
    if m and ":" in m.group("start"):
        start = parse_timecode(m.group("start"), fps)
        end = parse_timecode(m.group("end"), fps) if m.group("end") else None
        return start, end, line[: m.start()].strip()
    return None, None, line.strip()
