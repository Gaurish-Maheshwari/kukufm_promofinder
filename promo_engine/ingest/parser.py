"""Screenplay text -> Episodes made of timed Beats.

The input layout is never known in advance, so the parser is a tolerant state
machine that understands the common conventions at once and decides line by line.
Labels, timings and text may arrive on the same line or on separate lines, in
either order:

  [00:00:03] AVA: You think you can humiliate me?        (bracketed TC + NAME: line)
  00:03 - 00:06 | AVA | You think you can humiliate me?   (pipe / tab tables, ranges)
  00:05  ACTION: Ava slaps Chloe.                          (labelled action)
  SCENE 2 — INT. BALLROOM — NIGHT [00:20 - 00:45]          (scene heading, trailing TC)
  00:07 / AVA / (whispering) / You'll regret this.         (classic: TC line, NAME line, paren, text)
  **LADY JULIANA (Confused, Breathless):**                 (block layout: label line,
  Start: (00:13.50) | End: (00:14.30)                       timing line,
  "Why?"                                                    text)
  SCENE 01 / Scene heading: INT. CATHEDRAL – DAY / Scene start: 00:00.00
  EPISODE NUMBER: Episode 4 / EPISODE LOGLINE: …           (metadata header -> Episode.meta)
  EPISODE 4: The Contract                                  (several episodes per file)

Robustness:
- Every chunk is parsed by the main state machine AND, when that looks poor, by a
  structure-agnostic fallback ("any line containing a timecode is a beat"); the
  better-scoring parse wins and the choice is logged.
- A parse error in one episode never stops the run: that episode falls back or is skipped
  with a warning.
- Overlapping explicit ranges (camera shots running under dialogue) are kept and the
  beats are sorted by start time; start-only formats are clamped instead.
- Lines without a timestamp are interpolated by word count and flagged (Beat.timed=False).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..config import load_lexicons
from ..models import Beat, Episode, Scene, Show, SourceDoc
from ..timecode import RANGE_SEP, TC_RE, TC_TOKEN, parse_timecode, split_leading_timecode

EP_HEADER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*|\*\*|__)?\s*(?:S\d{1,2}\s*E|EPISODE|EPI|EP)\s*\.?\s*[#:\-–—]?\s*"
    r"(?P<num>\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten)\b"
    r"(?:\s*(?:of|/)\s*\d{1,3})?\s*[:\-–—.|]?\s*(?P<title>.*?)\s*(?:\*\*|__)?\s*$",
    re.I,
)
# "EPISODE NUMBER: Episode 4", "Episode No: 4", "EP #: 4"
EP_META_RE = re.compile(r"^\s*(?:EPISODE|EP)\s*(?:NUMBER|NUM|NO\.?|#)\s*[:=\-–]\s*(?:EPISODE|EP)?\s*\.?\s*#?\s*(?P<num>\d{1,4})\b", re.I)
SCENE_RE = re.compile(r"^\s*(?:(?:SCENE|SC)\.?\s*\d+[A-Z]?\s*[:.\-–—)|]?\s*)?(?:INT|EXT|INT\./EXT|INT/EXT|I/E|EST)[.\s/]")
SCENE_NUM_RE = re.compile(r"^\s*(?:SCENE|SC)\.?\s*#?\d+[A-Z]?\b", re.I)
SCENE_BARE_RE = re.compile(r"^\s*(?:SCENE|SC)\.?\s*#?\d+[A-Z]?\s*[:.\-–—]?\s*$", re.I)
SCENE_FIELD_RE = re.compile(r"^\s*(?:scene\s*)?(?P<field>heading|slugline|slug|location|setting|start|begin|starts|end|ends|stop)\s*[:=]\s*(?P<value>.*)$", re.I)
LABEL_RE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z0-9 .'’\-&/]{0,40}?)\s*(?P<paren>(?:\([^)]{0,60}\)\s*){0,3})\s*[:：]\s*(?P<text>.*)$"
)
CLASSIC_NAME_RE = re.compile(r"^(?P<name>[A-Z][A-Z0-9 .'’\-]{0,34}?)\s*(?P<paren>(?:\([^)]{0,40}\)\s*){0,3})\s*:?\s*$")
OFFSCREEN_RE = re.compile(r"^(?:V\.?\s?O\.?|O\.?\s?S\.?|O\.?\s?C\.?|CONT'?D|CONT’D|OFF[- ]?SCREEN|OFF[- ]?CAMERA|VOICE[- ]?OVER|PRE[- ]?LAP)$", re.I)


def _manner(paren: str) -> Optional[str]:
    """'(O.S.) (Firm)' -> 'off-screen, Firm'; '(Cold, Commanding)' -> 'Cold, Commanding'."""
    if not paren:
        return None
    parts = [p.strip() for p in re.findall(r"\(([^)]*)\)", paren) if p.strip()]
    out = []
    for p in parts:
        if OFFSCREEN_RE.match(p.replace(" ", "")) or OFFSCREEN_RE.match(p):
            out.append("off-screen" if not p.upper().startswith("V") else "voice-over")
        else:
            out.append(p)
    return ", ".join(out) or None
PAREN_ONLY_RE = re.compile(r"^\s*\(([^)]{1,60})\)\s*$")
TRANSITION_RE = re.compile(r"^\s*((SMASH |MATCH |HARD |JUMP )?CUT TO|FADE (IN|OUT|TO)|DISSOLVE TO|CUT TO BLACK|SMASH CUT|TO BE CONTINUED|END OF EPISODE|THE END)\b.*$", re.I)
META_KEYS = {
    "TITLE", "EPISODE TITLE", "SHOW", "SHOW TITLE", "SERIES", "WRITTEN BY", "WRITER", "WRITERS", "AUTHOR", "DURATION",
    "RUNTIME", "TOTAL RUNTIME", "LENGTH", "LOGLINE", "EPISODE LOGLINE", "SYNOPSIS", "EPISODE SYNOPSIS", "SUMMARY",
    "EPISODE SUMMARY", "GENRE", "DRAFT", "COPYRIGHT", "LANGUAGE", "FORMAT", "VERSION", "PAGE", "CONTINUITY",
    "CONTINUITY NOTES", "NOTES", "PRODUCTION NOTES", "CHARACTERS", "CAST", "TAGS", "THEME", "THEMES", "TONE",
    "TARGET AUDIENCE", "SEASON", "EPISODE ID", "SCRIPT ID", "ID", "DATE", "REVISION", "STATUS", "MOOD", "PREVIOUSLY",
}
SECTION_RE = re.compile(r"^\s*(?:-{2,}|={2,}|#{1,6}|\*{2,}|_{2,})?\s*(?:SCRIPT\s*(?:START|END|BEGINS?|ENDS?)|START\s+OF\s+SCRIPT|END\s+OF\s+SCRIPT|"
                        r"ACTIONS?\s+(?:AND|&)\s+DIALOGUES?|DIALOGUES?\s+(?:AND|&)\s+ACTIONS?|BEATS|SHOT\s*LIST|SCRIPT|SCREENPLAY|"
                        r"TRANSCRIPT|CONTENT|BODY)\s*:?\s*(?:-{2,}|={2,}|\*{2,}|_{2,})?\s*$", re.I)
BLOCK_TIMING_RE = re.compile(r"\b(?:start|from|begin)\s*[:=]\s*[\(\[]?\s*\d{1,2}:\d", re.I)
RULE_RE = re.compile(r"^\s*([-=*_~#]\s*){3,}$")
NAME_STOPWORDS = {"THE", "A", "AN", "NOTE", "NOTES", "WARNING", "TIP", "AND", "BUT", "SO", "THEN", "WHEN", "IF", "HOOK",
                  "CLIFFHANGER", "PROMO", "START", "END", "TIME", "STARTS", "ENDS", "EPISODE", "SCENE"}
BAD_SPEAKERS = {"START", "END", "TIME", "TIMESTAMP", "TC", "EPISODE", "EPISODE NUMBER", "EPISODE LOGLINE", "LOGLINE",
                "CONTINUITY NOTES", "SCENE START", "SCENE END", "SCENE HEADING", "NOTES", "TITLE", "DURATION", "IN", "OUT"}
TERMINAL_PUNCT = tuple('.!?…"”’)—-')
WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
MAX_EXPLICIT_BEAT_SECONDS = 45.0


@dataclass
class _RawBeat:
    kind: str
    text: str
    speaker: Optional[str] = None
    manner: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    raw: str = ""
    open: bool = False      # still accepting continuation lines


@dataclass
class _Pending:
    """A label that arrived before its text (block / classic layouts)."""
    kind: str                       # dialogue | action | camera | sfx | text
    speaker: Optional[str] = None
    manner: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None


@dataclass
class _EpisodeChunk:
    number: Optional[int]
    title: str
    lines: list[str] = field(default_factory=list)
    source: str = ""
    meta: dict[str, str] = field(default_factory=dict)


def _clean(line: str) -> str:
    """Remove markdown emphasis / bullets / odd spaces; keep the words."""
    line = line.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "").replace("\t", " \t ")
    line = re.sub(r"^\s*(?:[-*•▪◦]\s+|>\s+)", "", line)
    line = line.replace("**", "").replace("__", "")
    line = re.sub(r"^\s*#{1,6}\s+", "", line)
    return line.strip()


class ScreenplayParser:
    def __init__(self, cfg: Optional[dict] = None, lexicons: Optional[dict] = None):
        cfg = cfg or {}
        p = cfg.get("parser", {})
        self.fps = float(p.get("fps", 30))
        self.wps = float(p.get("words_per_second", 2.6))
        self.min_beat = float(p.get("min_beat_seconds", 0.8))
        self.max_est = float(p.get("max_estimated_beat_seconds", 8.0))
        self.max_explicit = float(p.get("max_explicit_beat_seconds", MAX_EXPLICIT_BEAT_SECONDS))
        self.split_on_reset = bool(p.get("split_on_timestamp_reset", True))
        lex = lexicons or load_lexicons()
        labels = lex.get("non_character_labels", {})
        self.label_kind: dict[str, str] = {}
        for kind, names in labels.items():
            for n in names:
                self.label_kind[self._norm_label(n)] = kind
        for n in ("SCENE", "SCENE HEADING", "SLUGLINE", "SLUG"):
            self.label_kind[n] = "scene"
        for n in ("DIALOGUE", "DIALOG", "LINE"):
            self.label_kind[n] = "dialogue_marker"
        self.strategy_log: list[str] = []

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _norm_label(s: str) -> str:
        return re.sub(r"\s+", " ", s.replace(".", "").replace("-", " ").replace("_", " ")).strip().upper()

    @staticmethod
    def _clean_speaker(name: str) -> str:
        name = re.sub(r"\((V\.?O\.?|O\.?S\.?|O\.?C\.?|CONT'?D|CONT’D)\)", "", name, flags=re.I)
        name = re.sub(r"\s+", " ", name).strip(" .:-")
        return name.upper()

    def _looks_like_name(self, label: str) -> bool:
        label = label.strip()
        if not label or len(label) > 35 or re.search(r"\d{2,}", label):
            return False
        words = label.replace("’", "'").split()
        if len(words) > 5 or label.upper() in BAD_SPEAKERS:
            return False
        articles = {"THE", "A", "AN"}
        if words[0].upper() in NAME_STOPWORDS and not (label.isupper() and len(words) > 1 and words[0].upper() in articles):
            return False      # "THE FORMER GROOM" is a name; "The" alone or "Note" is not
        return all(w[0].isupper() or w[0] in "'’" for w in words if w)

    def _is_meta(self, label: str) -> bool:
        return self._norm_label(label) in META_KEYS

    def _estimate(self, text: str) -> float:
        words = max(1, len(re.findall(r"\w+", text)))
        return min(self.max_est, max(self.min_beat, words / self.wps))

    def _label_kind(self, label: str) -> Optional[str]:
        k = self.label_kind.get(self._norm_label(label))
        if k:
            return k
        # "CAMERA 2", "SOUND FX (distant)", "ACTION – wide" -> first word(s)
        first = self._norm_label(label).split(" ")
        for n in (2, 1):
            k = self.label_kind.get(" ".join(first[:n]))
            if k and k != "dialogue_marker":
                return k
        return None

    # ---------------------------------------------------------- episode split
    def split_episodes(self, doc: SourceDoc) -> list[_EpisodeChunk]:
        lines = doc.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        chunks: list[_EpisodeChunk] = []
        current = _EpisodeChunk(number=doc.episode_hint, title="", source=doc.path)
        saw_header = False

        def has_content(ch: _EpisodeChunk) -> bool:
            return any(l.strip() for l in ch.lines)

        def start_new(number, title):
            nonlocal current, saw_header
            if has_content(current):
                is_preamble = not saw_header and not any(
                    split_leading_timecode(_clean(l), self.fps)[0] is not None for l in current.lines)
                if not is_preamble:      # drop title pages before the first header
                    chunks.append(current)
                elif current.meta:       # keep header metadata that came before the number line
                    pass
            carried = current.meta if (not saw_header and not chunks) else {}
            current = _EpisodeChunk(number=number, title=title, source=doc.path, meta=dict(carried))
            saw_header = True

        for ln in lines:
            cl = _clean(ln)
            _, _, rest = split_leading_timecode(cl, self.fps)
            mm = EP_META_RE.match(rest)
            if mm:
                n = int(mm.group("num"))
                if not saw_header or has_content(current) or current.number not in (None, n):
                    if saw_header and not has_content(current):
                        current.number = n            # the number line follows other metadata
                    else:
                        start_new(n, "")
                else:
                    current.number = n
                if doc.episode_hint is not None and doc.episode_hint != n and len([c for c in chunks]) == 0:
                    current.meta["_number_note"] = f"file name says {doc.episode_hint}, header says {n}; using header"
                continue
            m = EP_HEADER_RE.match(rest) if len(rest) < 90 else None
            if m and self._is_header(rest, m):
                num = m.group("num").lower()
                number = int(num) if num.isdigit() else WORD_NUM.get(num)
                title = re.sub(r"[\[\(]?\s*" + TC_TOKEN + r".*$", "", m.group("title") or "").strip(" -–—:|*#")
                start_new(number, title)
                continue
            current.lines.append(ln)
        if has_content(current):
            chunks.append(current)
        if not saw_header and self.split_on_reset and len(chunks) == 1:
            chunks = self._split_on_reset(chunks[0])
        return chunks

    @staticmethod
    def _is_header(rest: str, m: re.Match) -> bool:
        # Avoid "EP: I can't believe..." style dialogue: a header has a short title.
        title = m.group("title") or ""
        return len(title) <= 70 and not title.endswith("?")

    def _split_on_reset(self, chunk: _EpisodeChunk) -> list[_EpisodeChunk]:
        times: list[tuple[int, float]] = []
        for i, ln in enumerate(chunk.lines):
            s, _, _ = split_leading_timecode(_clean(ln), self.fps)
            if s is not None:
                times.append((i, s))
        cut_points = []
        for (i0, t0), (i1, t1) in zip(times, times[1:]):
            if t0 > 30 and t1 < 5 and t1 < t0 - 25:
                cut_points.append(i1)
        if not cut_points:
            return [chunk]
        out, prev = [], 0
        for k, cp in enumerate(cut_points + [len(chunk.lines)]):
            out.append(_EpisodeChunk(number=(chunk.number + k) if chunk.number else None, title="",
                                     lines=chunk.lines[prev:cp], source=chunk.source, meta=dict(chunk.meta) if k == 0 else {}))
            prev = cp
        return out

    # ------------------------------------------------------------ line parse
    def _parse_delimited(self, line: str) -> Optional[_RawBeat]:
        sep = "|" if line.count("|") >= 1 else ("\t" if "\t" in line else None)
        if not sep:
            return None
        fields = [f.strip() for f in line.split(sep)]
        fields = [f for f in fields if f]
        if len(fields) < 2:
            return None
        header_words = {"TIME", "TIMESTAMP", "TC", "START", "END", "IN", "OUT", "TYPE", "KIND", "ELEMENT", "CHARACTER",
                        "SPEAKER", "NAME", "TEXT", "LINE", "DIALOGUE", "DESCRIPTION", "ACTION", "CONTENT", "NOTES", "#", "NO"}
        if all(f.upper() in header_words for f in fields):
            return _RawBeat(kind="skip", text="")       # a table header row
        start = end = None
        kind = None
        speaker = None
        texts: list[str] = []
        range_re = re.compile(r"^(?:(?:start|end|from|to|in|out|time)\s*[:=]?\s*)?[\[\(]?\s*(" + TC_TOKEN + r")\s*[\]\)]?\s*(?:"
                              + RANGE_SEP + r"[\[\(]?\s*(" + TC_TOKEN + r")\s*[\]\)]?)?$", re.I)
        for f in fields:
            m = range_re.match(f)
            if m and (":" in m.group(1)) and start is None:
                start = parse_timecode(m.group(1), self.fps)
                end = parse_timecode(m.group(2), self.fps) if m.group(2) else None
                continue
            if m and ":" in m.group(1) and start is not None and end is None:
                end = parse_timecode(m.group(1), self.fps)
                continue
            lk = self._label_kind(f) if len(f) < 30 else None
            if lk and kind is None:
                kind = lk
                continue
            if speaker is None and not texts and self._looks_like_name(f) and f.upper() == f and len(fields) >= 3:
                speaker = self._clean_speaker(f)
                continue
            texts.append(f)
        if start is None and kind is None and speaker is None:
            return None
        text = " ".join(texts).strip()
        if not text:
            return None
        if kind in (None, "dialogue_marker"):
            kind = "dialogue" if speaker else "action"
        if kind == "vo":
            kind, speaker = "dialogue", speaker or "NARRATOR"
        manner = None
        pm = re.match(r"^\(([^)]{1,40})\)\s*(.*)$", text)
        if pm and kind == "dialogue":
            manner, text = pm.group(1), pm.group(2)
        return _RawBeat(kind=kind, text=text, speaker=speaker, manner=manner, start=start, end=end, raw=line)

    def _pending_from_label(self, label: str, paren: Optional[str], start, end) -> Optional[_Pending]:
        kind = self._label_kind(label)
        if kind == "vo":
            return _Pending("dialogue", "NARRATOR" if self._norm_label(label) in ("NARRATOR", "NARRATION", "VO", "V O", "VOICEOVER", "VOICE OVER") else self._clean_speaker(label), paren, start, end)
        if kind in ("action", "camera", "sfx", "text"):
            return _Pending(kind, None, paren, start, end)
        if kind is None and self._looks_like_name(label):
            return _Pending("dialogue", self._clean_speaker(label), paren, start, end)
        return None

    def parse_chunk(self, chunk: _EpisodeChunk) -> list[_RawBeat]:
        beats: list[_RawBeat] = []
        pending: Optional[_Pending] = None
        pending_tc: tuple[Optional[float], Optional[float]] = (None, None)
        pending_meta: Optional[str] = None
        seen_timed = False

        def emit(b: _RawBeat):
            nonlocal seen_timed
            beats.append(b)
            if b.start is not None:
                seen_timed = True

        for ln in chunk.lines:
            raw = ln.rstrip()
            line = _clean(raw)
            if not line:
                if beats:
                    beats[-1].open = False
                pending_meta = None
                continue
            if RULE_RE.match(line) or SECTION_RE.match(line):
                continue
            # metadata header lines (logline, notes…) -> Episode.meta, never dialogue
            lm0 = LABEL_RE.match(line)
            if lm0 and self._is_meta(lm0.group("label")) and split_leading_timecode(line, self.fps)[0] is None:
                key = self._norm_label(lm0.group("label")).lower().replace(" ", "_")
                chunk.meta[key] = lm0.group("text").strip()
                pending_meta = key
                continue
            if pending_meta and not seen_timed and not beats and split_leading_timecode(line, self.fps)[0] is None \
                    and not LABEL_RE.match(line) and not SCENE_NUM_RE.match(line):
                chunk.meta[pending_meta] += " " + line         # wrapped metadata value
                continue
            pending_meta = None
            # 1) a pure timing line: "Start: (00:01.00) | End: (00:04.80)", "00:07", "[00:01 - 00:04]"
            start, end, rest = split_leading_timecode(line, self.fps)
            if start is not None and not rest:
                if pending is not None and pending.start is None:
                    pending.start, pending.end = start, end
                else:
                    pending_tc = (start, end)
                continue
            # 2) delimited table rows (but not "LABEL: Start: (..) | End: (..)" — that pipe is a range separator)
            if ("|" in line or "\t" in line) and not BLOCK_TIMING_RE.search(line):
                b = self._parse_delimited(line)
                if b and b.kind == "skip":
                    continue
                if b:
                    emit(b)
                    pending = None
                    continue
            if start is None and pending_tc[0] is not None and pending is None:
                start, end = pending_tc
                pending_tc = (None, None)
            # 3) scene fields: "Scene heading: INT. …", "Scene start: 00:00.00"
            sf = SCENE_FIELD_RE.match(rest)
            if sf and (rest.lower().startswith("scene") or sf.group("field").lower() in ("heading", "slugline", "slug")):
                fld, val = sf.group("field").lower(), sf.group("value").strip()
                last_scene = next((b for b in reversed(beats) if b.kind == "scene"), None)
                content_after = last_scene is not None and beats[-1] is not last_scene
                if fld in ("heading", "slugline", "slug", "location", "setting"):
                    if last_scene is not None and not content_after and SCENE_BARE_RE.match(last_scene.text):
                        last_scene.text = val or last_scene.text
                    else:
                        emit(_RawBeat(kind="scene", text=val, start=start, end=None, raw=raw))
                elif fld in ("start", "begin", "starts"):
                    t = parse_timecode(val.strip("()[] "), self.fps) if val else None
                    if t is None:
                        m2 = TC_RE.search(val)
                        t = parse_timecode(m2.group(0), self.fps) if m2 else None
                    if last_scene is not None and t is not None and last_scene.start is None:
                        last_scene.start = t
                continue
            # 4) scene heading
            if SCENE_RE.match(rest) or SCENE_NUM_RE.match(rest):
                heading = re.sub(r"^\s*(?:SCENE|SC)\.?\s*#?\d+[A-Z]?\s*[:.\-–—)|]?\s*", "", rest, flags=re.I).strip() or rest
                emit(_RawBeat(kind="scene", text=heading, start=start, end=None, raw=raw))
                pending = None
                continue
            # 5) transitions (kept: they can be cliffhanger markers)
            if TRANSITION_RE.match(rest):
                if pending is not None:          # "**CAMERA:** / Start… / Smash cut to black." keeps the block's timing
                    s0 = pending.start if pending.start is not None else start
                    e0 = pending.end if pending.start is not None else end
                    emit(_RawBeat(kind=pending.kind if pending.kind != "dialogue" else "action", text=rest.rstrip(":"),
                                  start=s0, end=e0, raw=raw))
                else:
                    emit(_RawBeat(kind="action", text=rest.rstrip(":"), start=start, end=end, raw=raw))
                pending = None
                continue
            # 6) parenthetical on its own line
            pm = PAREN_ONLY_RE.match(rest)
            if pm and pending is not None and pending.kind == "dialogue":
                pending.manner = pm.group(1)
                continue
            # 7) LABEL: text   (or LABEL: alone -> pending label)
            lm = LABEL_RE.match(rest)
            if lm and not re.match(r"^\d", lm.group("label")):
                label = lm.group("label").strip()
                text = lm.group("text").strip()
                paren = _manner(lm.group("paren") or "")
                kind = self._label_kind(label)
                if kind == "scene":
                    if text:
                        emit(_RawBeat(kind="scene", text=text, start=start, end=None, raw=raw))
                    pending = None
                    continue
                if text:
                    # inline timing after the label: "AVA: Start: (00:01) | End: (00:02) Hello"
                    s2, e2, t2 = split_leading_timecode(text, self.fps)
                    if s2 is not None:
                        start, end, text = (start if start is not None else s2), (end if end is not None else e2), t2
                if not text:
                    p = self._pending_from_label(label, paren, start, end)
                    if p is not None:
                        pending = p
                        continue
                    # "Actions and dialogue:" and other section labels: ignore
                    if not self._looks_like_name(label):
                        continue
                else:
                    if kind in ("action", "sfx", "text", "camera", "vo"):
                        if kind == "vo":
                            emit(_RawBeat(kind="dialogue", text=text, speaker="NARRATOR", start=start, end=end, raw=raw))
                        else:
                            emit(_RawBeat(kind=kind, text=text, start=start, end=end, raw=raw, open=True))
                        pending = None
                        continue
                    if kind is None and self._looks_like_name(label):
                        pm2 = re.match(r"^\(([^)]{1,40})\)\s*(.*)$", text)
                        if pm2:
                            paren, text = pm2.group(1), pm2.group(2)
                        emit(_RawBeat(kind="dialogue", text=text, speaker=self._clean_speaker(label),
                                      manner=paren, start=start, end=end, raw=raw, open=True))
                        pending = None
                        continue
            # 8) classic: NAME alone on a line (optionally with (paren))
            cm = CLASSIC_NAME_RE.match(rest)
            if cm and cm.group("name").upper() == cm.group("name") and self._looks_like_name(cm.group("name")) \
                    and len(rest) <= 60 and not TC_RE.search(rest):
                p = self._pending_from_label(cm.group("name"), _manner(cm.group("paren") or ""), start, end)
                if p is not None:
                    pending = p
                    continue
            # 9) body text for a pending label
            if pending is not None:
                s0 = pending.start if pending.start is not None else start
                e0 = pending.end if pending.start is not None else end
                if s0 is None and pending_tc[0] is not None:
                    s0, e0 = pending_tc
                    pending_tc = (None, None)
                emit(_RawBeat(kind=pending.kind, text=rest, speaker=pending.speaker, manner=pending.manner,
                              start=s0, end=e0, raw=raw, open=True))
                pending = None
                continue
            # 10) continuation of an open beat / wrapped line
            if start is None and beats:
                prev = beats[-1]
                if prev.kind != "scene" and (prev.open or not prev.text.endswith(TERMINAL_PUNCT) or rest[:1].islower()):
                    prev.text = f"{prev.text} {rest}".strip()
                    prev.raw += "\n" + raw
                    continue
            # 11) default: an action line
            emit(_RawBeat(kind="action", text=rest, start=start, end=end, raw=raw))
            pending = None
        return [b for b in beats if b.text.strip()]

    # ------------------------------------------------- fallback (structure-agnostic)
    def parse_chunk_scan(self, chunk: _EpisodeChunk) -> list[_RawBeat]:
        """Last-resort reader: every line holding a timecode starts a beat; the text is whatever
        remains on that line (or the next non-empty lines). Speaker = an ALL-CAPS 'NAME:' if present."""
        beats: list[_RawBeat] = []
        lines = [_clean(l) for l in chunk.lines]
        i = 0
        while i < len(lines):
            line = lines[i]
            tcs = list(TC_RE.finditer(line))
            tcs = [m for m in tcs if ":" in m.group(0)]
            if not tcs:
                i += 1
                continue
            start = parse_timecode(tcs[0].group(0), self.fps)
            end = parse_timecode(tcs[1].group(0), self.fps) if len(tcs) > 1 else None
            text = TC_RE.sub(" ", line)
            text = re.sub(r"\b(start|end|from|to|time|timestamp|in|out)\b\s*[:=]?", " ", text, flags=re.I)
            text = re.sub(r"[\[\]\(\)\|]+", " ", text).strip(" :-–—")
            label_line = lines[i - 1] if i > 0 else ""
            j = i + 1
            body = []
            while not text and j < len(lines) and lines[j] and not TC_RE.search(lines[j]):
                body.append(lines[j])
                j += 1
            text = (text + " " + " ".join(body)).strip()
            speaker = None
            kind = "action"
            lm = LABEL_RE.match(text) or LABEL_RE.match(label_line + " x") if not text.startswith('"') else None
            src_label = None
            if LABEL_RE.match(text):
                m = LABEL_RE.match(text)
                src_label, text = m.group("label"), m.group("text")
            elif label_line and LABEL_RE.match(label_line) and not LABEL_RE.match(label_line).group("text"):
                src_label = LABEL_RE.match(label_line).group("label")
            if src_label:
                k = self._label_kind(src_label)
                if k in ("action", "camera", "sfx", "text"):
                    kind = k
                elif self._looks_like_name(src_label):
                    kind, speaker = "dialogue", self._clean_speaker(src_label)
            del lm
            if text:
                beats.append(_RawBeat(kind=kind, text=text, speaker=speaker, start=start, end=end, raw=line))
            i = max(j, i + 1)
        return beats

    def _quality(self, raws: list[_RawBeat]) -> float:
        """0–1: how believable a parse is (timed, no timecodes leaking into text, sane speakers)."""
        content = [b for b in raws if b.kind != "scene"]
        if not content:
            return 0.0
        timed = sum(b.start is not None for b in content) / len(content)
        leak = sum(bool(TC_RE.search(b.text) and re.search(r"\d:\d\d", b.text)) or bool(re.match(r"^(start|end)\b", b.text, re.I))
                   for b in content) / len(content)
        bad_spk = sum(1 for b in content if b.speaker and (b.speaker in BAD_SPEAKERS or len(b.speaker) > 35)) / len(content)
        return round(0.6 * timed + 0.25 * (1 - leak) + 0.15 * (1 - bad_spk), 4)

    def parse_chunk_robust(self, chunk: _EpisodeChunk, warnings: list[str]) -> list[_RawBeat]:
        main: list[_RawBeat] = []
        q_main = -1.0
        try:
            main = self.parse_chunk(chunk)
            q_main = self._quality(main)
        except Exception as exc:  # noqa: BLE001 - never let one episode kill the run
            warnings.append(f"Main parser failed on {chunk.source} (ep {chunk.number}): {exc}; using fallback reader.")
        content = [b for b in main if b.kind != "scene"]
        broken = (not content or q_main < 0 or
                  sum(bool(re.match(r"^(start|end)\b", b.text, re.I)) or bool(b.speaker and b.speaker in BAD_SPEAKERS)
                      for b in content) / len(content) > 0.15 or
                  sum(b.start is not None for b in content) / len(content) < 0.3)
        if not broken:          # the main reader only gives way when its output is clearly wrong
            return main
        try:
            alt = self.parse_chunk_scan(chunk)
            q_alt = self._quality(alt)
        except Exception as exc:  # noqa: BLE001
            alt, q_alt = [], -1.0
            warnings.append(f"Fallback reader failed on {chunk.source}: {exc}")
        if q_alt > q_main + 0.05 and len(alt) >= 0.5 * len(main):
            self.strategy_log.append(f"{chunk.source}: fallback reader (quality {q_alt:.2f} vs {q_main:.2f})")
            warnings.append(f"{chunk.source}: unusual layout, used the structure-agnostic reader (quality {q_alt:.2f} vs {q_main:.2f}).")
            return alt
        return main

    # -------------------------------------------------------------- timing
    def resolve_times(self, raws: list[_RawBeat], warnings: list[str]) -> tuple[list[tuple[float, float, bool]], float, bool]:
        n = len(raws)
        starts: list[Optional[float]] = [b.start for b in raws]
        timed = [s is not None for s in starts]
        content = [b for b in raws if b.kind != "scene"]
        explicit_ranges = sum(1 for b in content if b.start is not None and b.end is not None) / max(1, len(content))
        overlap_mode = explicit_ranges >= 0.5
        # normalise show-absolute timecodes so every episode starts near 0
        first = min((s for s in starts if s is not None), default=None)
        offset = 0.0
        if first is not None and first > 30:
            offset = first
            starts = [None if s is None else s - offset for s in starts]
            warnings.append(f"Timestamps start at {first:.1f}s; treated as show-absolute and shifted to 0 (offset kept).")
        if not overlap_mode:
            # start-only formats: a backwards jump is a typo -> clamp
            last = None
            bad = 0
            for i, s in enumerate(starts):
                if s is None:
                    continue
                if last is not None and s < last - 0.5:
                    bad += 1
                    starts[i] = last
                last = starts[i]
            if bad:
                warnings.append(f"{bad} timestamp(s) went backwards and were clamped.")
        if starts and starts[0] is None:
            starts[0] = 0.0
        est = [self._estimate(b.text) if b.kind != "scene" else 0.0 for b in raws]
        i = 0
        while i < n:
            if starts[i] is not None:
                i += 1
                continue
            a = i - 1
            b = i
            while b < n and starts[b] is None:
                b += 1
            if b < n and starts[b] >= starts[a]:  # interpolate between anchors a and b
                total_est = sum(est[a:b]) or 1.0
                span = starts[b] - starts[a]
                t = starts[a]
                for k in range(a, b - 1):
                    t += span * (est[k] / total_est)
                    starts[k + 1] = t
            else:      # trailing untimed beats (or anchors out of order)
                for k in range(i, b if b < n else n):
                    starts[k] = starts[k - 1] + est[k - 1]
            i = b
        out: list[tuple[float, float, bool]] = []
        capped = 0
        for k in range(n):
            s = float(starts[k])
            e_raw = raws[k].end if raws[k].kind != "scene" else None   # a scene's range is not a beat length
            e = (e_raw - offset) if e_raw is not None else None
            if e is not None and e - s > self.max_explicit:
                capped += 1                                            # typo guard: 01:00 written as 10:00
                e = None
            nxt = next((starts[m] for m in range(k + 1, n) if starts[m] > s), None) if overlap_mode else (starts[k + 1] if k + 1 < n else None)
            if e is None or e <= s:
                if raws[k].kind == "scene":
                    e = s
                elif nxt is not None and nxt > s and (nxt - s) <= self.max_explicit:
                    e = nxt
                else:
                    e = s + max(est[k], self.min_beat)
                    if nxt is None:      # final beat: microdramas hold on the last frame
                        e = max(e, s + 2.0)
            out.append((round(s, 3), round(float(e), 3), timed[k]))
        if capped:
            warnings.append(f"{capped} beat(s) had implausible lengths (> {self.max_explicit:.0f}s) and were re-estimated.")
        return out, offset, overlap_mode

    # --------------------------------------------------------------- public
    def parse_docs(self, docs: list[SourceDoc], title: str = "Untitled show") -> Show:
        show = Show(title=title)
        by_number: dict[int, Episode] = {}
        next_auto = 1
        for doc in docs:
            try:
                chunks = self.split_episodes(doc)
            except Exception as exc:  # noqa: BLE001
                show.warnings.append(f"Could not split {doc.path} into episodes ({exc}); treating it as one episode.")
                chunks = [_EpisodeChunk(number=doc.episode_hint, title="", lines=doc.text.splitlines(), source=doc.path)]
            for chunk in chunks:
                raws = self.parse_chunk_robust(chunk, show.warnings)
                if not raws:
                    show.warnings.append(f"No screenplay lines found in {chunk.source}")
                    continue
                number = chunk.number
                if chunk.meta.get("_number_note"):
                    show.warnings.append(f"{chunk.source}: {chunk.meta.pop('_number_note')}")
                if number is None or number in by_number:
                    if number in by_number:
                        prev = by_number[number]
                        if len(prev.beats) >= len(raws):
                            show.warnings.append(f"Episode {number} appears twice; kept {prev.source}, skipped {chunk.source}")
                            continue
                        show.warnings.append(f"Episode {number} appears twice; replaced {prev.source} with larger {chunk.source}")
                    else:
                        while next_auto in by_number:
                            next_auto += 1
                        number = next_auto
                        show.warnings.append(f"No episode number for {chunk.source}; assigned {number}")
                try:
                    ep = self._build_episode(number, chunk, raws)
                except Exception as exc:  # noqa: BLE001
                    show.warnings.append(f"Episode {number} ({chunk.source}) skipped: {exc}")
                    continue
                by_number[number] = ep
                next_auto = max(next_auto, number + 1)
        eps = [by_number[k] for k in sorted(by_number)]
        # a stray untimed document among properly timed episodes (notes, a synopsis) is not an episode
        timed_eps = [e for e in eps if e.parse_confidence >= 0.5]
        if len(timed_eps) >= max(2, 0.6 * len(eps)):
            for e in eps:
                if e.parse_confidence == 0:
                    show.warnings.append(f"Ignored {e.source}: no timestamps, unlike the rest of the show (notes or synopsis?).")
            eps = [e for e in eps if e.parse_confidence > 0]
        show.episodes = eps
        return show

    def _build_episode(self, number: int, chunk: _EpisodeChunk, raws: list[_RawBeat]) -> Episode:
        ep = Episode(number=number, title=chunk.title, source=chunk.source,
                     meta={k: v for k, v in chunk.meta.items() if not k.startswith("_")})
        if not ep.title:
            ep.title = (chunk.meta.get("episode_title") or chunk.meta.get("title") or "").strip()
        times, offset, overlap_mode = self.resolve_times(raws, ep.warnings)
        rows = []
        scene_id = 0
        for order, (rb, (s, e, timed)) in enumerate(zip(raws, times)):
            if rb.kind == "scene":
                scene_id += 1
            rows.append((s, order, rb, e, timed, scene_id))
        if overlap_mode:
            rows.sort(key=lambda r: (r[0], r[1]))     # explicit ranges may overlap: order by start
        for i, (s, _, rb, e, timed, sid) in enumerate(rows):
            ep.beats.append(Beat(idx=i, episode=number, start=s, end=e, kind=rb.kind, text=rb.text.strip(),
                                 speaker=rb.speaker, manner=rb.manner, scene_id=sid, timed=timed, raw=rb.raw))
        # scenes
        cur: Optional[Scene] = None
        for b in ep.beats:
            if cur is None or b.scene_id != cur.id:
                if cur:
                    ep.scenes.append(cur)
                heading = b.text if b.kind == "scene" else "(untitled scene)"
                cur = Scene(id=b.scene_id, episode=number, heading=heading, start=b.start, end=b.end, first_beat=b.idx, last_beat=b.idx)
            cur.end = max(cur.end, b.end)
            cur.last_beat = b.idx
        if cur:
            ep.scenes.append(cur)
        content = [b for b in ep.beats if b.kind != "scene"]
        ep.parse_confidence = round(sum(b.timed for b in content) / max(1, len(content)), 3)
        if ep.parse_confidence < 0.5:
            ep.warnings.append(f"Only {ep.parse_confidence:.0%} of lines had timestamps; others were interpolated.")
        if offset:
            ep.warnings.append(f"offset={offset:.3f}")
        return ep


def parse_show(docs: list[SourceDoc], cfg: Optional[dict] = None, title: str = "Untitled show") -> Show:
    return ScreenplayParser(cfg).parse_docs(docs, title=title)
