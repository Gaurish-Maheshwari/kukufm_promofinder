"""Would a first-time viewer follow this clip? Returns a 0–1 score and the reasons."""
from __future__ import annotations

import re

from ..models import Beat, Episode
from .characters import characters_in


def standalone_score(ep: Episode, first: int, last: int) -> tuple[float, list[str]]:
    beats = ep.beats[first:last + 1]
    content = [b for b in beats if b.kind != "scene"]
    if not content:
        return 0.0, ["empty window"]
    score = 1.0
    reasons: list[str] = []
    # 1) the first spoken line leans on something we never saw
    first_dlg = next((b for b in content[:6] if b.kind == "dialogue"), None)
    if first_dlg is not None:
        ctx_types = first_dlg.signals.get("context_types", [])
        opens_clip = first_dlg.start - content[0].start <= 3.0    # first spoken line, even if a shot comes first
        if "opening_pronoun" in ctx_types and opens_clip:
            score -= 0.15
            reasons.append(f"opens on an unexplained pronoun: “{first_dlg.text[:50]}”")
        if "opening_reply" in ctx_types and opens_clip:
            score -= 0.15
            reasons.append("opens mid-conversation (first line is a reply)")
        if "opening_continuation" in ctx_types and opens_clip:
            score -= 0.2
            reasons.append("opens mid-sentence (line starts with '…')")
    # an episode that "picks up directly from" the previous cliffhanger needs context in its first seconds
    notes = (ep.meta.get("continuity_notes") or ep.meta.get("continuity") or ep.meta.get("previously") or "").lower()
    if notes and content[0].start < 12 and re.search(r"pick(s|ing)? up|directly|immediately|continuous|follows? (directly|on)", notes):
        score -= 0.1
        reasons.append("opens on the carried-over cliffhanger from the previous episode")
    # 2) back-references anywhere in the clip
    backrefs = [b for b in content if "back_reference" in b.signals.get("context_types", [])]
    if backrefs:
        pen = min(0.25, 0.08 * len(backrefs))
        score -= pen
        reasons.append(f"{len(backrefs)} line(s) refer to earlier events")
    # 3) the line just before the clip was a question this clip answers
    if first > 0:
        prev = ep.beats[first - 1]
        if prev.kind == "dialogue" and prev.text.rstrip().endswith("?") and prev.scene_id == content[0].scene_id:
            score -= 0.12
            reasons.append("starts right after an unanswered question (answer without the question)")
    # 4) characters talked about but never shown
    present, offscreen = characters_in(beats)
    if len(offscreen) > 1:
        pen = min(0.2, 0.06 * (len(offscreen) - 1))
        score -= pen
        reasons.append(f"mentions off-screen characters: {', '.join(sorted(offscreen))}")
    if len(present) > 4:
        score -= 0.1
        reasons.append(f"{len(present)} speaking characters — hard to follow in 30 s")
    # 5) continuity: many scene changes inside one clip
    scenes = {b.scene_id for b in content}
    if len(scenes) > 2:
        score -= 0.05 * (len(scenes) - 2)
        reasons.append(f"crosses {len(scenes)} scenes")
    # bonus: clean entry at a scene start
    if beats[0].kind == "scene" or (first > 0 and ep.beats[first - 1].kind == "scene"):
        score += 0.08
    return max(0.0, min(1.0, score)), reasons


def window_beats(ep: Episode, first: int, last: int) -> list[Beat]:
    return ep.beats[first:last + 1]
