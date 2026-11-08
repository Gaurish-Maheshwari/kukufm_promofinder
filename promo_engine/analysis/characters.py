"""Character registry: who speaks, how often, where they first appear, and
which beats mention which characters (used by the stand-alone check)."""
from __future__ import annotations

import re
from collections import defaultdict

from ..models import Show

IGNORE = {"NARRATOR", "ALL", "EVERYONE", "CROWD", "VOICE", "MAN", "WOMAN", "GUARD", "GUEST", "GUESTS", "WAITER", "NURSE", "DOCTOR",
          "OFF-SCREEN VOICE", "VOICES", "BOTH", "TOGETHER"}
HONORIFICS = {"LADY", "LORD", "SIR", "MR", "MRS", "MS", "MISS", "DUKE", "DUCHESS", "DR", "KING", "QUEEN", "PRINCE",
              "PRINCESS", "YOUNG", "OLD", "MASTER", "MADAM", "DAME", "COUNT", "COUNTESS", "BARON", "AUNT", "UNCLE"}


def canonical_names(speakers: set[str]) -> dict[str, str]:
    """'LADY JULIANA' -> 'JULIANA' when JULIANA also speaks; 'LORD ASHCROFT' stays as is."""
    canon = {}
    for name in speakers:
        parts = name.replace(".", "").split()
        if len(parts) > 1 and parts[0] in HONORIFICS and " ".join(parts[1:]) in speakers:
            canon[name] = " ".join(parts[1:])
        else:
            canon[name] = name
    return canon


def build_registry(show: Show) -> dict[str, dict]:
    reg: dict[str, dict] = {}
    speakers = {b.speaker for ep in show.episodes for b in ep.beats if b.kind == "dialogue" and b.speaker}
    canon = canonical_names(speakers)
    for ep in show.episodes:
        for b in ep.beats:
            if b.speaker:
                b.signals["speaker_canon"] = canon.get(b.speaker, b.speaker)
            if b.kind == "dialogue" and b.speaker and b.speaker not in IGNORE:
                key = canon.get(b.speaker, b.speaker)
                r = reg.setdefault(key, {"lines": 0, "first_episode": ep.number, "first_time": b.start,
                                         "episodes": set(), "aliases": set(), "also_credited_as": set()})
                if key != b.speaker:
                    r["also_credited_as"].add(b.speaker)
                r["lines"] += 1
                r["episodes"].add(ep.number)
    # aliases: first and last token of multi-word names ("ETHAN STERLING" -> ETHAN, STERLING)
    for name, r in reg.items():
        parts = [p for p in re.split(r"[\s.]+", name) if len(p) > 2 and p not in HONORIFICS
                 and p not in {"THE", "AND", "WITH", "OF"}]
        r["aliases"] = {name} | set(parts) | set(r["also_credited_as"])
    # mentions: which known characters each beat refers to
    alias_to_name: dict[str, str] = {}
    for name, r in reg.items():
        for a in r["aliases"]:
            alias_to_name.setdefault(a, name)
    pattern = re.compile(r"\b(" + "|".join(sorted((re.escape(a) for a in alias_to_name), key=len, reverse=True)) + r")\b", re.I) if alias_to_name else None
    for ep in show.episodes:
        for b in ep.beats:
            mentions = set()
            if pattern:
                for m in pattern.finditer(b.text):
                    mentions.add(alias_to_name.get(m.group(1).upper(), m.group(1).upper()))
            b.signals["mentions"] = sorted(mentions)
    total = sum(r["lines"] for r in reg.values()) or 1
    for name, r in reg.items():
        r["share"] = round(r["lines"] / total, 4)
        r["main"] = r["share"] >= 0.06
        r["episodes"] = sorted(r["episodes"])
        r["aliases"] = sorted(r["aliases"])
        r["also_credited_as"] = sorted(r["also_credited_as"])
    show.characters = dict(sorted(reg.items(), key=lambda kv: -kv[1]["lines"]))
    return show.characters


def characters_in(beats) -> tuple[set[str], set[str]]:
    """(on-screen characters, characters only talked about) for a list of beats."""
    present, mentioned = set(), set()
    for b in beats:
        if b.kind == "dialogue" and b.speaker:
            present.add(b.signals.get("speaker_canon", b.speaker))
        if b.kind in ("action", "camera"):
            present.update(b.signals.get("mentions", []))
        elif b.kind == "dialogue":
            mentioned.update(b.signals.get("mentions", []))
    return present, mentioned - present
