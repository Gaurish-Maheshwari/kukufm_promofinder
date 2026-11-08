#!/usr/bin/env bash
# Optional: cut raw promo segments from episode videos for quick preview.
# Usage: VIDEO_DIR=/path/to/episodes PATTERN='Episode_%02d.mp4' bash ffmpeg_cuts.sh
# (No music, captions or effects are added — the brief asks only for the moments.)
set -euo pipefail
VIDEO_DIR="${VIDEO_DIR:-./videos}"
PATTERN="${PATTERN:-Episode_%02d.mp4}"
OUT="${OUT:-./promo_previews}"
mkdir -p "$OUT"
src() { printf "$VIDEO_DIR/$PATTERN" "$1"; }

# P02 — rank 2, post 1: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 50.000 -to 67.400 -i "$(src 2)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P02_seg1.mp4"
ffmpeg -hide_banner -loglevel error -y -ss 87.000 -to 100.400 -i "$(src 3)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P02_seg2.mp4"
: > "$OUT/P02_list.txt"
echo "file '$(basename "$OUT/P02_seg1.mp4")'" >> "$OUT/P02_list.txt"
echo "file '$(basename "$OUT/P02_seg2.mp4")'" >> "$OUT/P02_list.txt"
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$OUT/P02_list.txt" -c copy "$OUT/P02.mp4"

# P03 — rank 3, post 2: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 43.000 -to 100.400 -i "$(src 3)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P03_seg1.mp4"
mv "$OUT/P03_seg1.mp4" "$OUT/P03.mp4"

# P01 — rank 1, post 3: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 74.000 -to 96.400 -i "$(src 4)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P01_seg1.mp4"
mv "$OUT/P01_seg1.mp4" "$OUT/P01.mp4"

# P05 — rank 5, post 4: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 29.000 -to 55.400 -i "$(src 3)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P05_seg1.mp4"
mv "$OUT/P05_seg1.mp4" "$OUT/P05.mp4"

# P07 — rank 7, post 5: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 14.000 -to 50.400 -i "$(src 1)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P07_seg1.mp4"
mv "$OUT/P07_seg1.mp4" "$OUT/P07.mp4"

# P10 — rank 10, post 6: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 50.000 -to 97.400 -i "$(src 1)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P10_seg1.mp4"
mv "$OUT/P10_seg1.mp4" "$OUT/P10.mp4"

# P12 — rank 12, post 7: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 67.000 -to 99.862 -i "$(src 2)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P12_seg1.mp4"
mv "$OUT/P12_seg1.mp4" "$OUT/P12.mp4"

# P04 — rank 4, post 8: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 0.000 -to 28.400 -i "$(src 6)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P04_seg1.mp4"
mv "$OUT/P04_seg1.mp4" "$OUT/P04.mp4"

# P14 — rank 14, post 9: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 67.000 -to 71.400 -i "$(src 2)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P14_seg1.mp4"
ffmpeg -hide_banner -loglevel error -y -ss 30.000 -to 67.400 -i "$(src 2)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P14_seg2.mp4"
: > "$OUT/P14_list.txt"
echo "file '$(basename "$OUT/P14_seg1.mp4")'" >> "$OUT/P14_list.txt"
echo "file '$(basename "$OUT/P14_seg2.mp4")'" >> "$OUT/P14_list.txt"
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$OUT/P14_list.txt" -c copy "$OUT/P14.mp4"

# P09 — rank 9, post 10: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 3.000 -to 38.400 -i "$(src 5)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P09_seg1.mp4"
mv "$OUT/P09_seg1.mp4" "$OUT/P09.mp4"

# P08 — rank 8, post 11: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 50.000 -to 90.400 -i "$(src 5)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P08_seg1.mp4"
mv "$OUT/P08_seg1.mp4" "$OUT/P08.mp4"

# P06 — rank 6, post 12: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 28.000 -to 80.400 -i "$(src 7)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P06_seg1.mp4"
mv "$OUT/P06_seg1.mp4" "$OUT/P06.mp4"

# P11 — rank 11, post 13: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 63.000 -to 87.400 -i "$(src 8)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P11_seg1.mp4"
mv "$OUT/P11_seg1.mp4" "$OUT/P11.mp4"

# P13 — rank 13, post 14: Mock judge: scored from cue words.
ffmpeg -hide_banner -loglevel error -y -ss 45.000 -to 95.631 -i "$(src 6)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P13_seg1.mp4"
mv "$OUT/P13_seg1.mp4" "$OUT/P13.mp4"

# P15 — rank 15, post 15: Builds quickly from a quiet open and cuts on a question nobody answers; the billionaire/he
ffmpeg -hide_banner -loglevel error -y -ss 23.000 -to 52.400 -i "$(src 6)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P15_seg1.mp4"
mv "$OUT/P15_seg1.mp4" "$OUT/P15.mp4"

echo "Done: $OUT"