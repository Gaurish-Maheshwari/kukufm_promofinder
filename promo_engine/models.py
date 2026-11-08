"""Plain dataclasses shared by every stage of the pipeline.

The timeline model is deliberately simple: an Episode is an ordered list of
Beats (one line of dialogue, one action, one scene heading...) and every Beat
has a start and end time in seconds. Everything downstream (candidates,
promos, exports, comparison) speaks in (episode, start, end).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class SourceDoc:
    """A raw text document pulled out of a file, folder or zip."""
    name: str               # file name, e.g. "Episode 03.pdf"
    path: str               # path relative to the input root (zip members use "a.zip!/b.txt")
    text: str
    kind: str               # txt | pdf | docx | md | srt | vtt | csv | json
    episode_hint: Optional[int] = None   # episode number guessed from the file name


@dataclass
class Beat:
    idx: int                 # position inside the episode (0-based)
    episode: int
    start: float             # seconds from episode start
    end: float
    kind: str                # dialogue | action | camera | scene | sfx | text | vo
    text: str
    speaker: Optional[str] = None
    manner: Optional[str] = None       # parenthetical, e.g. "(whispering)"
    scene_id: int = 0
    timed: bool = True                 # False when the time was interpolated
    raw: str = ""
    signals: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def display(self) -> str:
        if self.kind == "dialogue" and self.speaker:
            m = f" ({self.manner})" if self.manner else ""
            return f"{self.speaker}{m}: {self.text}"
        if self.kind == "scene":
            return f"[SCENE] {self.text}"
        if self.kind == "camera":
            return f"[CAMERA] {self.text}"
        if self.kind in ("sfx", "text", "vo"):
            return f"[{self.kind.upper()}] {self.text}"
        return f"({self.text})"


@dataclass
class Scene:
    id: int
    episode: int
    heading: str
    start: float
    end: float
    first_beat: int
    last_beat: int


@dataclass
class Episode:
    number: int
    title: str
    source: str
    beats: list[Beat] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parse_confidence: float = 1.0      # share of beats that carried an explicit timestamp

    meta: dict[str, str] = field(default_factory=dict)   # logline, continuity notes, … from the file header

    @property
    def duration(self) -> float:
        return max((b.end for b in self.beats), default=0.0)

    def span_end(self, i: int, j: int) -> float:
        """End of a clip covering beats i..j. Beats can overlap (a camera shot runs while a
        line is spoken), so the clip ends at the latest end inside the window, not at beat j's end."""
        if j < i:
            return self.beats[i].end
        return max(b.end for b in self.beats[i:j + 1])


@dataclass
class Show:
    title: str
    episodes: list[Episode] = field(default_factory=list)
    characters: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def episode(self, number: int) -> Optional[Episode]:
        for ep in self.episodes:
            if ep.number == number:
                return ep
        return None

    @property
    def total_seconds(self) -> float:
        return sum(e.duration for e in self.episodes)


@dataclass
class Segment:
    episode: int
    start: float
    end: float
    first_beat: int
    last_beat: int

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Promo:
    id: str
    segments: list[Segment]
    kind: str = "continuous"           # continuous | montage_episode | montage_cross
    score: float = 0.0                 # final 0–100
    heuristic_score: float = 0.0
    llm_score: Optional[float] = None
    breakdown: dict[str, float] = field(default_factory=dict)
    hook: dict[str, Any] = field(default_factory=dict)          # text, type, at (s from promo start)
    cliffhanger: dict[str, Any] = field(default_factory=dict)   # text, type
    why: str = ""
    tropes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    rank: int = 0
    post_order: int = 0
    post_rationale: str = ""
    variants: dict[str, dict[str, float]] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)
    source: str = "rules"              # rules | rules+llm
    llm_notes: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.segments)

    @property
    def episodes(self) -> list[int]:
        out: list[int] = []
        for s in self.segments:
            if s.episode not in out:
                out.append(s.episode)
        return out

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["duration"] = round(self.duration, 2)
        d["episodes"] = self.episodes
        return d


def promo_from_dict(d: dict[str, Any]) -> Promo:
    segs = [Segment(**{k: s[k] for k in ("episode", "start", "end", "first_beat", "last_beat")})
            for s in d.get("segments", [])]
    fields = {k: v for k, v in d.items() if k in Promo.__dataclass_fields__ and k != "segments"}
    return Promo(segments=segs, **fields)
