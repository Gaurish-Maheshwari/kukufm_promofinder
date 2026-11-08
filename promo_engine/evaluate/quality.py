"""Self-check: flag every promo with the specific way it might be a bad pick,
and summarise where the tool picks badly across the whole run."""
from __future__ import annotations

from collections import Counter

from ..models import Promo, Show

FLAG_TEXT = {
    "weak_hook": "Weak hook — nothing in the first 3 s clearly stops the scroll",
    "late_hook": "Hook lands after 3 s",
    "soft_ending": "Soft ending — the last beat partly resolves the tension",
    "needs_context": "May need backstory to follow",
    "length_out_of_range": "Length outside the 20–60 s window",
    "interpolated_timing": "Some timestamps were interpolated — check IN/OUT on the timeline",
    "spoiler_risk": "Reveals a late twist — post later",
    "jump_cuts": "Stitched from several moments — check continuity",
    "visual_hook": "Hook is a visual action — depends on how it was shot",
    "llm_disagrees": "LLM judge and rules disagree strongly — review by hand",
    "below_min_score": "Below the minimum score — shown only because nothing else qualified",
}

KNOWN_FAILURE_MODES = [
    ("Visual-only beats", "If a key moment is only in the picture (a look, a reveal shot) and the screenplay line is bland, rules under-score it."),
    ("Sarcasm and subtext", "'Oh, how nice' scores as resolution; the cue lexicon reads words, not tone. The LLM pass fixes most of these."),
    ("Recurring callbacks", "Lines that reference earlier episodes ('like that night') are penalised even when the scene still lands for new viewers."),
    ("Over-reliance on '?'", "A question at the end looks like a cliffhanger even when it is rhetorical."),
    ("Stitched promos", "Montages are scored conservatively; editors' best multi-moment edits are the most likely misses."),
    ("Timestamps", "When lines lack timestamps, IN/OUT points are interpolated from word counts and can drift by 1–2 s."),
]


def flag_promo(p: Promo, f: dict, cfg: dict) -> list[str]:
    lo, hi = float(cfg["promo"]["min_seconds"]), float(cfg["promo"]["max_seconds"])
    flags = []
    if f.get("hook", 0) < 0.4:
        flags.append("weak_hook")
    elif f.get("hook_at", 0) > float(cfg["promo"].get("hook_window_seconds", 3)):
        flags.append("late_hook")
    if f.get("cliffhanger", 0) < 0.35 or f.get("resolution_at_end", 0) > 0.3:
        flags.append("soft_ending")
    if f.get("standalone", 1) < 0.6:
        flags.append("needs_context")
    if not (lo - 0.5 <= p.duration <= hi + 0.5):
        flags.append("length_out_of_range")
    if f.get("timing_confidence", 1) < 0.8:
        flags.append("interpolated_timing")
    if f.get("spoiler", 0) > 0.5:
        flags.append("spoiler_risk")
    if len(p.segments) > 1:
        flags.append("jump_cuts")
    if p.hook.get("type_key") == "physical" and p.hook.get("text", "").startswith("("):
        flags.append("visual_hook")
    llm = f.get("llm")
    if llm and f.get("heuristic_score") is not None and abs(llm["overall"] * 10 - f["heuristic_score"]) > 30:
        flags.append("llm_disagrees")
    return flags


def quality_report(promos: list[Promo], show: Show) -> dict:
    counts = Counter(fl for p in promos for fl in p.flags)
    n = len(promos) or 1
    clean = sum(1 for p in promos if not set(p.flags) - {"visual_hook", "jump_cuts"})
    worst = sorted(promos, key=lambda p: (-len(p.flags), p.score))[:5]
    parse = [{"episode": e.number, "confidence": e.parse_confidence, "warnings": [w for w in e.warnings if not w.startswith("offset=")]}
             for e in show.episodes if e.parse_confidence < 0.9 or any(not w.startswith("offset=") for w in e.warnings)]
    return {
        "flag_counts": {k: {"count": v, "share": round(v / n, 3), "meaning": FLAG_TEXT.get(k, k)} for k, v in counts.most_common()},
        "clean_promos": clean,
        "clean_share": round(clean / n, 3),
        "review_first": [{"id": p.id, "rank": p.rank, "flags": [FLAG_TEXT.get(f, f) for f in p.flags]} for p in worst if p.flags],
        "parse_issues": parse,
        "known_failure_modes": [{"mode": a, "detail": b} for a, b in KNOWN_FAILURE_MODES],
    }
