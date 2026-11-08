"""Editor-ready formats.

- CMX3600 EDL: imports into Premiere Pro, DaVinci Resolve, Avid, Final Cut (via conversion).
  Each episode is a reel (EP001…). Promos are laid end-to-end on the record
  timeline with a 2-second gap, each event commented with the promo id and hook.
- Markers CSV: one row per promo segment for quick manual placement.
- ffmpeg script: optional — if the episode video files exist, cuts each promo's
  raw segments (no music/overlays, per the brief) so an editor can preview them.
"""
from __future__ import annotations

import csv
import io

from ..timecode import fmt, smpte

FPS = 30


def edl_all(run: dict, pre_roll: float = 0.0, post_roll: float = 0.4, fps: int = FPS) -> str:
    durations = {e["number"]: e["duration"] for e in run["show"]["episodes"]}
    lines = [f"TITLE: KUKU PROMOS {run['show']['title'][:40].upper()}", "FCM: NON-DROP FRAME", ""]
    rec = 3600.0  # record timeline starts at 01:00:00:00
    ev = 1
    for p in sorted(run["promos"], key=lambda x: x["post_order"]):
        for k, s in enumerate(p["segments"], 1):
            a = max(0.0, s["start"] - pre_roll)
            b = min(durations.get(s["episode"], s["end"] + post_roll), s["end"] + post_roll)
            dur = b - a
            reel = f"EP{int(s['episode']):03d}"
            lines.append(f"{ev:03d}  {reel:<8} AA/V  C        {smpte(a, fps)} {smpte(b, fps)} {smpte(rec, fps)} {smpte(rec + dur, fps)}")
            lines.append(f"* FROM CLIP NAME: EPISODE {int(s['episode']):03d}")
            lines.append(f"* COMMENT: {p['id']} rank {p['rank']} post {p['post_order']} seg {k}/{len(p['segments'])} | "
                         f"HOOK: {p['hook'].get('type', '')} | CLIFF: {p['cliffhanger'].get('type', '')}")
            lines.append("")
            rec += dur
            ev += 1
        rec += 2.0
    return "\n".join(lines)


def markers_csv(run: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Marker Name", "Episode", "In", "Out", "Duration", "Color", "Notes"])
    colors = ["Red", "Orange", "Yellow", "Green", "Cyan", "Blue", "Purple"]
    for p in run["promos"]:
        for k, s in enumerate(p["segments"], 1):
            w.writerow([f"{p['id']} (rank {p['rank']}) seg {k}", s["episode"], fmt(s["start"], "hms"), fmt(s["end"], "hms"),
                        f"{s['end'] - s['start']:.2f}", colors[(p["rank"] - 1) % len(colors)], p["why"]])
    return buf.getvalue()


def ffmpeg_script(run: dict, pre_roll: float = 0.0, post_roll: float = 0.4) -> str:
    L = [
        "#!/usr/bin/env bash",
        "# Optional: cut raw promo segments from episode videos for quick preview.",
        "# Usage: VIDEO_DIR=/path/to/episodes PATTERN='Episode_%02d.mp4' bash ffmpeg_cuts.sh",
        "# (No music, captions or effects are added — the brief asks only for the moments.)",
        "set -euo pipefail",
        'VIDEO_DIR="${VIDEO_DIR:-./videos}"',
        'PATTERN="${PATTERN:-Episode_%02d.mp4}"',
        'OUT="${OUT:-./promo_previews}"',
        'mkdir -p "$OUT"',
        "src() { printf \"$VIDEO_DIR/$PATTERN\" \"$1\"; }",
        "",
    ]
    for p in sorted(run["promos"], key=lambda x: x["post_order"]):
        parts = []
        L.append(f"# {p['id']} — rank {p['rank']}, post {p['post_order']}: {p['why'][:90]}")
        for k, s in enumerate(p["segments"], 1):
            a = max(0.0, s["start"] - pre_roll)
            b = s["end"] + post_roll
            part = f'"$OUT/{p["id"]}_seg{k}.mp4"'
            parts.append(part)
            L.append(f'ffmpeg -hide_banner -loglevel error -y -ss {a:.3f} -to {b:.3f} -i "$(src {int(s["episode"])})" '
                     f'-c:v libx264 -preset veryfast -crf 18 -c:a aac {part}')
        if len(parts) > 1:
            lst = f'"$OUT/{p["id"]}_list.txt"'
            L.append(f": > {lst}")
            for part in parts:
                L.append(f"echo \"file '$(basename {part})'\" >> {lst}")
            L.append(f'ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i {lst} -c copy "$OUT/{p["id"]}.mp4"')
        else:
            L.append(f'mv {parts[0]} "$OUT/{p["id"]}.mp4"')
        L.append("")
    L.append('echo "Done: $OUT"')
    return "\n".join(L)
