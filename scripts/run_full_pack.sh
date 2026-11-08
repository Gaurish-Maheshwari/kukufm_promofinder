#!/usr/bin/env bash
# Run the tool on the real input pack and write the raw-outputs deliverable.
#   bash scripts/run_full_pack.sh [INPUT] [MANUAL]
# Defaults: INPUT=data/input  MANUAL=data/manual_promos/my_manual_promos.csv (used only if it exists)
set -euo pipefail
cd "$(dirname "$0")/.."
INPUT="${1:-data/input}"
MANUAL="${2:-data/manual_promos/my_manual_promos.csv}"
OUT="outputs/raw_outputs_full_pack"
PY="${PY:-python3}"

if [ -z "$(ls -A "$INPUT" 2>/dev/null | grep -v -e README.md -e .gitkeep)" ]; then
  echo "No screenplays in $INPUT. Put the input pack (folder/zip/pdf/txt) there first." >&2; exit 1
fi
MAN_ARGS=()
[ -f "$MANUAL" ] && MAN_ARGS=(-m "$MANUAL") && echo "Comparing against $MANUAL"

echo "== 1/4 parse check"
$PY -m promo_engine parse -i "$INPUT" | tee "$OUT.parse.log"
echo "== 2/4 main run (uses LLM_API_KEY from .env if set)"
$PY -m promo_engine run -i "$INPUT" "${MAN_ARGS[@]}" -o "$OUT" --with-timeline --show 15
echo "== 3/4 rules-only run for comparison"
$PY -m promo_engine run -i "$INPUT" "${MAN_ARGS[@]}" -o "$OUT/rules_only" --no-llm --quiet --show 0
echo "== 4/4 platform presets"
for p in tiktok reels shorts; do
  $PY -m promo_engine run -i "$INPUT" -o "$OUT/platform_$p" --platform "$p" --quiet --show 0 >/dev/null
done
mv "$OUT.parse.log" "$OUT/parse.log"
if [ -f "$MANUAL" ]; then
  echo "== metrics with your manual promos"
  $PY scripts/generate_metrics.py --input "$INPUT" --manual "$MANUAL" --skip-tests
fi
echo "Done → $OUT"
