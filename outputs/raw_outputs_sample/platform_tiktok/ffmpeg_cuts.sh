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

# P03 — rank 3, post 1: Opens on a physical shock at 0.0s (“A guard grabs Ava's wrist. She doesn't move.”) and cut
ffmpeg -hide_banner -loglevel error -y -ss 43.000 -to 78.400 -i "$(src 3)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P03_seg1.mp4"
mv "$OUT/P03_seg1.mp4" "$OUT/P03.mp4"

# P04 — rank 4, post 2: Opens on a shocking line at 0.0s (“Regret? You're nothing. A nobody who scrubs…”) and cuts
ffmpeg -hide_banner -loglevel error -y -ss 50.000 -to 60.400 -i "$(src 1)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P04_seg1.mp4"
ffmpeg -hide_banner -loglevel error -y -ss 87.000 -to 100.400 -i "$(src 3)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P04_seg2.mp4"
: > "$OUT/P04_list.txt"
echo "file '$(basename "$OUT/P04_seg1.mp4")'" >> "$OUT/P04_list.txt"
echo "file '$(basename "$OUT/P04_seg2.mp4")'" >> "$OUT/P04_list.txt"
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$OUT/P04_list.txt" -c copy "$OUT/P04.mp4"

# P05 — rank 5, post 3: Opens on a physical shock at 0.0s (“Two guards grab Ava by the arms and drag her…”) and cu
ffmpeg -hide_banner -loglevel error -y -ss 67.000 -to 71.400 -i "$(src 2)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P05_seg1.mp4"
ffmpeg -hide_banner -loglevel error -y -ss 43.000 -to 67.400 -i "$(src 2)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P05_seg2.mp4"
: > "$OUT/P05_list.txt"
echo "file '$(basename "$OUT/P05_seg1.mp4")'" >> "$OUT/P05_list.txt"
echo "file '$(basename "$OUT/P05_seg2.mp4")'" >> "$OUT/P05_list.txt"
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$OUT/P05_list.txt" -c copy "$OUT/P05.mp4"

# P01 — rank 1, post 4: Opens on a shocking line at 0.0s (“How dare you show your face here!”) and cuts on an unex
ffmpeg -hide_banner -loglevel error -y -ss 74.000 -to 96.400 -i "$(src 4)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P01_seg1.mp4"
mv "$OUT/P01_seg1.mp4" "$OUT/P01.mp4"

# P11 — rank 11, post 5: Opens on a confrontation at 0.0s (“Security, we have a cleaner who thinks she's…”) and cut
ffmpeg -hide_banner -loglevel error -y -ss 29.000 -to 55.400 -i "$(src 3)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P11_seg1.mp4"
mv "$OUT/P11_seg1.mp4" "$OUT/P11.mp4"

# P07 — rank 7, post 6: Opens on a physical shock at 0.0s (“Two guards grab Ava by the arms and drag her…”) and cu
ffmpeg -hide_banner -loglevel error -y -ss 67.000 -to 99.862 -i "$(src 2)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P07_seg1.mp4"
mv "$OUT/P07_seg1.mp4" "$OUT/P07.mp4"

# P02 — rank 2, post 7: Opens on a reveal at 0.0s (“Chloe enters holding a paternity test envelope.”) and cuts on 
ffmpeg -hide_banner -loglevel error -y -ss 63.000 -to 87.400 -i "$(src 8)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P02_seg1.mp4"
mv "$OUT/P02_seg1.mp4" "$OUT/P02.mp4"

# P06 — rank 6, post 8: Opens on a physical shock at 0.0s (“A hooded figure lunges from the balcony and…”) and cut
ffmpeg -hide_banner -loglevel error -y -ss 0.000 -to 28.400 -i "$(src 6)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P06_seg1.mp4"
mv "$OUT/P06_seg1.mp4" "$OUT/P06.mp4"

# P09 — rank 9, post 9: Opens on a shocking line at 0.0s (“I didn't die, Chloe. I was hidden. From people…”) and c
ffmpeg -hide_banner -loglevel error -y -ss 15.000 -to 44.400 -i "$(src 5)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P09_seg1.mp4"
mv "$OUT/P09_seg1.mp4" "$OUT/P09.mp4"

# P15 — rank 15, post 10: Opens on a shocking line at 0.0s (“You'll regret this, Miss Vance.”) and cuts on an unreso
ffmpeg -hide_banner -loglevel error -y -ss 46.000 -to 68.400 -i "$(src 1)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P15_seg1.mp4"
mv "$OUT/P15_seg1.mp4" "$OUT/P15.mp4"

# P10 — rank 10, post 11: Opens on a romantic moment at 0.0s (“Ethan kisses her.”) and cuts on a reveal that hasn't 
ffmpeg -hide_banner -loglevel error -y -ss 50.000 -to 81.400 -i "$(src 5)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P10_seg1.mp4"
mv "$OUT/P10_seg1.mp4" "$OUT/P10.mp4"

# P08 — rank 8, post 12: Opens on a reveal at 0.0s (“The DNA results. Open it. Prove you're the…”) and cuts on an u
ffmpeg -hide_banner -loglevel error -y -ss 66.000 -to 70.400 -i "$(src 8)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P08_seg1.mp4"
ffmpeg -hide_banner -loglevel error -y -ss 42.000 -to 66.400 -i "$(src 8)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P08_seg2.mp4"
: > "$OUT/P08_list.txt"
echo "file '$(basename "$OUT/P08_seg1.mp4")'" >> "$OUT/P08_list.txt"
echo "file '$(basename "$OUT/P08_seg2.mp4")'" >> "$OUT/P08_list.txt"
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$OUT/P08_list.txt" -c copy "$OUT/P08.mp4"

# P16 — rank 16, post 13: Opens on a shocking line at 0.0s (“Clumsy girl! Clean it up. On your knees.”) and cuts on 
ffmpeg -hide_banner -loglevel error -y -ss 14.000 -to 39.400 -i "$(src 1)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P16_seg1.mp4"
mv "$OUT/P16_seg1.mp4" "$OUT/P16.mp4"

# P12 — rank 12, post 14: Opens on a confrontation at 0.0s (“My father died in a car crash. That's what…”) and cuts 
ffmpeg -hide_banner -loglevel error -y -ss 28.000 -to 51.400 -i "$(src 7)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P12_seg1.mp4"
mv "$OUT/P12_seg1.mp4" "$OUT/P12.mp4"

# P17 — rank 17, post 15: Builds quickly from a quiet open and cuts on the writers' own cliffhanger beat; reads clea
ffmpeg -hide_banner -loglevel error -y -ss 72.000 -to 97.400 -i "$(src 1)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P17_seg1.mp4"
mv "$OUT/P17_seg1.mp4" "$OUT/P17.mp4"

# P14 — rank 14, post 16: Builds quickly from a quiet open and cuts on a question nobody answers; the billionaire/he
ffmpeg -hide_banner -loglevel error -y -ss 0.000 -to 26.400 -i "$(src 5)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P14_seg1.mp4"
mv "$OUT/P14_seg1.mp4" "$OUT/P14.mp4"

# P13 — rank 13, post 17: Builds quickly from a quiet open and cuts on a question nobody answers; the billionaire/he
ffmpeg -hide_banner -loglevel error -y -ss 23.000 -to 52.400 -i "$(src 6)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P13_seg1.mp4"
mv "$OUT/P13_seg1.mp4" "$OUT/P13.mp4"

# P18 — rank 18, post 18: Opens on a physical shock at 0.0s (“An hour later, the east wing was burning.”) and cuts o
ffmpeg -hide_banner -loglevel error -y -ss 45.000 -to 72.400 -i "$(src 6)" -c:v libx264 -preset veryfast -crf 18 -c:a aac "$OUT/P18_seg1.mp4"
mv "$OUT/P18_seg1.mp4" "$OUT/P18.mp4"

echo "Done: $OUT"