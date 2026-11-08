"""Per-beat signals: hook strength, cliffhanger strength, resolution, intensity,
context-dependence and tropes. Computed once per show, reused by every window."""
from __future__ import annotations

import re
from typing import Optional

from ..models import Show
from .lexicon import Lexicon

HOOK_LABEL = {
    "physical": "Physical shock",
    "reveal": "Reveal",
    "shocking_line": "Shocking line",
    "confrontation": "Confrontation",
    "romance": "Romantic moment",
    "status_mention": "Status mention",
    "emotional_peak": "Emotional peak",
}
CLIFF_LABEL = {
    "interrupted": "Line cut off mid-sentence",
    "open_question": "Unanswered question",
    "reveal_pending": "Reveal about to land",
    "arrival": "Someone/something arrives",
    "threat": "Threat hangs in the air",
    "decision_pending": "Decision pending",
    "explicit_marker": "Writer-marked cliffhanger",
    "tease_next": "Cuts right before the payoff",
    "episode_end": "Episode-ending cliffhanger",
}


_QUOTES = "\"“”‘’'«»"


def _strip_quotes(text: str) -> str:
    t = text.strip()
    if len(t) >= 2 and t[0] in _QUOTES:
        t = t[1:]
        if t and t[-1] in _QUOTES:
            t = t[:-1]
    return t.strip()


def _caps_ratio(text: str) -> float:
    words = re.findall(r"[A-Za-z]{3,}", text)
    if not words:
        return 0.0
    return sum(1 for w in words if w.isupper()) / len(words)


def annotate_show(show: Show, lex: Optional[Lexicon] = None) -> Lexicon:
    lex = lex or Lexicon()
    for ep in show.episodes:
        content = [b for b in ep.beats if b.kind != "scene"]
        last_idx = content[-1].idx if content else -1
        for b in ep.beats:
            s = b.signals
            if b.kind == "scene" or not b.text.strip():
                s.update(hook=0.0, hook_type=None, cliff=0.0, cliff_type=None, resolution=0.0,
                         intensity=0.0, context=0.0, context_types=[], tropes=[], reveal=0.0)
                continue
            # analyse the words, not the typography: drop wrapping quotes so ^-anchored cues work
            text = _strip_quotes(b.text)
            text_full = text
            hook, hook_type, hook_hits = lex.combine(lex.hook, text)
            if b.manner:
                # delivery notes ("Cold, Commanding", "Weeping") show emotion, never a physical event
                m_score, _, _ = lex.combine([g for g in lex.hook if g.name in ("emotional_peak", "confrontation")], b.manner)
                if m_score:
                    hook = 1 - (1 - hook) * (1 - 0.5 * m_score)
                    hook_type = hook_type or "emotional_peak"
            # punctuation and delivery cues
            excl = text.count("!")
            caps = _caps_ratio(text) if b.kind == "dialogue" else 0.0
            if b.kind == "dialogue":
                short_punch = 1.0 if len(text.split()) <= 6 and (excl or text.endswith("?")) else 0.0
                hook = 1 - (1 - hook) * (1 - 0.12 * min(excl, 2)) * (1 - 0.25 * caps) * (1 - 0.1 * short_punch)
            cliff, cliff_type, _ = lex.combine(lex.cliff, text)
            resolution, _, _ = lex.combine([lex.resolution], text)
            if cliff_type == "open_question" and resolution > 0:
                cliff *= 0.6
            if b.kind == "camera":
                # shot descriptions hint at what's on screen but are not the moment itself
                hook *= 0.6
                if cliff_type != "explicit_marker":
                    cliff *= 0.6
            elif b.kind == "sfx":
                hook *= 0.8
            ctx, _, ctx_hits = lex.combine(lex.context, text)
            tropes = lex.tropes_in(text_full)
            intensity = min(1.0, 0.75 * hook + 0.12 * min(excl, 2) / 2 + 0.13 * caps + (0.1 if tropes else 0.0))
            if b.kind == "camera":
                intensity *= 0.7
            s.update(
                hook=round(hook, 4), hook_type=hook_type, hook_hits=hook_hits,
                cliff=round(cliff, 4), cliff_type=cliff_type,
                resolution=round(resolution, 4),
                intensity=round(intensity, 4),
                context=round(ctx, 4), context_types=sorted(ctx_hits),
                tropes=tropes,
                reveal=round(lex.combine([g for g in lex.hook if g.name in ("reveal", "physical")], text_full)[0], 4),
                is_last=b.idx == last_idx,
            )
    return lex


def intensity_curve(show: Show, bin_seconds: float = 5.0) -> list[dict]:
    """Max beat intensity per time bin per episode — feeds the heatmap."""
    rows = []
    for ep in show.episodes:
        nbins = max(1, int(ep.duration // bin_seconds) + 1)
        bins = [0.0] * nbins
        for b in ep.beats:
            k = min(nbins - 1, int(b.start // bin_seconds))
            bins[k] = max(bins[k], b.signals.get("intensity", 0.0))
        rows.append({"episode": ep.number, "bin_seconds": bin_seconds, "values": [round(v, 3) for v in bins],
                     "duration": round(ep.duration, 2)})
    return rows
