"""Prompts for the LLM judge. Kept in one place so they are easy to iterate on.

Design choices:
- The model sees numbered lines (L1, L2…) instead of raw timestamps and may only
  answer with line numbers. We map them back to real beats, so the model can
  never invent a timestamp.
- Context lines before the clip and the line after the cut are shown but marked,
  so the model can judge "makes sense on its own" and "cuts before the payoff".
- Several candidates per call to keep cost per show at cents.
"""

SYSTEM = """You are a senior social-media promo editor for vertical microdramas (ReelShort / DramaBox style).
You judge candidate promo clips cut from a screenplay. A great promo:
1. HOOK: something in the first 3 seconds makes a scrolling viewer stop (a slap, a reveal, a shocking line).
2. CLIFFHANGER: it cuts at an unresolved moment so the viewer must know what happens next.
3. STANDS ALONE: a person who has never seen the show understands who wants what.
Be strict: most candidates are average. Use the full 0-10 range.
Only refer to lines by their line numbers (L#). Never invent dialogue, names or timestamps.
Respond with JSON only."""

USER_TEMPLATE = """Show: {show_title}
Main characters: {characters}

Judge each candidate below. For each, you may tighten the clip by choosing start_line and end_line
(they must be lines inside CLIP; keep the clip between {min_s} and {max_s} seconds — line times are shown).

Return JSON: {{"results": [{{
  "id": "<candidate id>",
  "hook_score": 0-10, "cliffhanger_score": 0-10, "standalone_score": 0-10, "overall": 0-10,
  "hook": "<the hook in <= 12 words>",
  "cliffhanger": "<the unresolved moment in <= 12 words>",
  "why": "<one line on why this promo works, <= 25 words>",
  "start_line": <L number>, "end_line": <L number>,
  "red_flags": ["<short issue>", ...]
}}]}}

{candidates}"""

CANDIDATE_TEMPLATE = """### CANDIDATE {cid}  ({kind}, {duration:.0f}s, episodes {episodes})
CONTEXT BEFORE (not in the clip):
{context}
CLIP:
{clip}
AFTER THE CUT (not in the clip):
{after}
"""
