"""Compiled cue lexicons (see config/lexicons.yaml)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..config import load_lexicons


@dataclass
class CueGroup:
    name: str
    weight: float
    patterns: list[re.Pattern]

    def hits(self, text: str) -> int:
        return sum(1 for p in self.patterns if p.search(text))


BAD_PATTERNS: list[str] = []


def _compile(pats) -> list[re.Pattern]:
    """Compile cue patterns; a typo in a hand-edited lexicon skips that pattern instead of crashing."""
    out = []
    for p in pats or []:
        try:
            out.append(re.compile(str(p), re.I))
        except re.error as exc:
            BAD_PATTERNS.append(f"{p!r}: {exc}")
    return out


class Lexicon:
    def __init__(self, data: Optional[dict] = None):
        data = data or load_lexicons()
        self.raw = data
        self.hook = [CueGroup(k, float(v["weight"]), _compile(v["patterns"])) for k, v in data.get("hook", {}).items()]
        self.cliff = [CueGroup(k, float(v["weight"]), _compile(v["patterns"])) for k, v in data.get("cliffhanger", {}).items()]
        r = data.get("resolution", {})
        self.resolution = CueGroup("resolution", float(r.get("weight", 0.6)), _compile(r.get("patterns")))
        self.context = [CueGroup(k, float(v["weight"]), _compile(v["patterns"])) for k, v in data.get("context_dependence", {}).items()]
        self.tropes = {k: _compile(v) for k, v in data.get("tropes", {}).items()}
        self.trope_value = {k: float(v) for k, v in data.get("trope_value", {}).items()}

    @staticmethod
    def combine(groups: list[CueGroup], text: str) -> tuple[float, Optional[str], dict[str, int]]:
        """Noisy-OR of matching groups. Returns (score 0–1, strongest group, hits per group)."""
        miss = 1.0
        best, best_w = None, 0.0
        hits: dict[str, int] = {}
        for g in groups:
            h = g.hits(text)
            if not h:
                continue
            hits[g.name] = h
            w = min(0.99, g.weight * (1 + 0.15 * (h - 1)))   # several hits in a group nudge it up
            miss *= (1 - w)
            if w > best_w:
                best, best_w = g.name, w
        return 1 - miss, best, hits

    def tropes_in(self, text: str) -> list[str]:
        return [k for k, pats in self.tropes.items() if any(p.search(text) for p in pats)]
