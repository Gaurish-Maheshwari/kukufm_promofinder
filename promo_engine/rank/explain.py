"""Human-readable hook / cliffhanger / 'why it works' lines for rules mode.
(When an LLM is connected it rewrites these; the rules version is the fallback.)"""
from __future__ import annotations

from ..analysis.features import CLIFF_LABEL, HOOK_LABEL
from ..models import Show

CLIFF_PHRASE = {
    "interrupted": "a line cut off mid-sentence",
    "open_question": "a question nobody answers",
    "reveal_pending": "a reveal that hasn't landed yet",
    "arrival": "an unexpected arrival",
    "threat": "a threat left hanging",
    "decision_pending": "a decision nobody has made yet",
    "tease_next": "the split second before the payoff",
    "episode_end": "the episode's own cliffhanger",
    "explicit_marker": "the writers' own cliffhanger beat",
    None: "an unresolved beat",
}
TROPE_NAME = {
    "slap_humiliation": "public-humiliation",
    "hidden_identity": "hidden-identity",
    "rich_powerful": "billionaire/heir",
    "betrayal_cheating": "betrayal",
    "pregnancy_baby": "secret-pregnancy",
    "marriage_contract": "marriage/contract",
    "revenge": "revenge",
    "family_rejection": "family-rejection",
    "supernatural": "fantasy",
    "danger_rescue": "danger-and-rescue",
    "jilted_betrayal": "jilted-at-the-altar",
    "royalty_status": "hidden-nobility",
    "trial_accusation": "false-accusation",
}


def _short(text: str, n: int = 70) -> str:
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    cut = text.rfind(" ", 0, n - 1)
    return text[: cut if cut > n // 2 else n - 1].rstrip(" ,.;:") + "…"


def hook_info(c, show: Show) -> dict:
    seg = c.segments[0]
    ep = show.episode(seg.episode)
    k = c.features.get("hook_beat")
    if k is None:
        k = next((b.idx for b in ep.beats[seg.first_beat:seg.last_beat + 1] if b.kind != "scene"), seg.first_beat)
    b = ep.beats[k]
    htype = c.features.get("hook_type")
    return {"text": _short(b.display(), 160), "type": HOOK_LABEL.get(htype, "Opening line (weak hook)"),
            "type_key": htype, "at": round(b.start - seg.start, 2), "episode": ep.number, "timestamp": round(b.start, 2),
            "score": round(float(c.features.get("hook", 0.0)), 3)}


def cliff_info(c, show: Show) -> dict:
    seg = c.segments[-1]
    ep = show.episode(seg.episode)
    k = c.features.get("cliff_beat", seg.last_beat)
    b = ep.beats[k]
    ctype = c.features.get("cliff_type")
    return {"text": _short(b.display(), 160), "type": CLIFF_LABEL.get(ctype, "Soft ending (weak cliffhanger)"),
            "type_key": ctype, "episode": ep.number, "timestamp": round(b.start, 2),
            "score": round(float(c.features.get("cliffhanger", 0.0)), 3)}


def why_line(c, hook: dict, cliff: dict) -> str:
    f = c.features
    parts = []
    if f.get("hook", 0) >= 0.5:
        quote = hook['text'].split(': ', 1)[-1].strip('()').strip().strip('"“”')
        parts.append(f"opens on a {hook['type'].lower()} at {hook['at']:.1f}s (“{_short(quote, 48)}”)")
    else:
        parts.append("builds quickly from a quiet open")
    parts.append(f"cuts on {CLIFF_PHRASE.get(f.get('cliff_type'), CLIFF_PHRASE[None])}")
    tail = ""
    tropes = f.get("tropes") or []
    if tropes and f.get("standalone", 0) >= 0.75:
        tail = f"; the {TROPE_NAME.get(tropes[0], tropes[0])} setup needs no backstory"
    elif tropes:
        tail = f"; sells the {TROPE_NAME.get(tropes[0], tropes[0])} trope"
    elif f.get("standalone", 0) >= 0.8:
        tail = "; reads clearly to a first-time viewer"
    if c.kind == "montage_cross":
        tail += f" — stitches {len(c.segments)} escalating moments across episodes {', '.join(str(s.episode) for s in c.segments)}"
    elif c.kind == "montage_episode":
        tail += " — flash-forward cold open, then rewinds to the build-up"
    s = " and ".join(parts) + tail + "."
    return s[0].upper() + s[1:]
