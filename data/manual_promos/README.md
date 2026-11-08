# Your manual promos

Put the promos you picked by hand here, e.g. `my_manual_promos.csv`, then run:

```bash
python -m promo_engine run -i data/input -m data/manual_promos/my_manual_promos.csv
```

The tool tells you how many of your promos it found, shows them side by side with its own,
and explains every miss (too long, stitched, or out-ranked, and by which signal).

Accepted formats (pick whichever is easiest):

| Format | How |
|---|---|
| CSV (recommended) | Copy `manual_promos_TEMPLATE.csv`. One row per segment. |
| Google Sheet / Excel | Same columns → File ▸ Download ▸ CSV (or upload the `.xlsx`). |
| JSON | `[{"id":"M1","segments":[{"episode":3,"start":"00:41","end":"01:15"}],"hook":"…"}]` |
| Plain notes (.txt/.md) | One promo per line: `M1: Ep 3 00:41-01:15 \| hook: the slap \| cliff: who are you?` — stitched: `Ep 12 01:05-01:40 + Ep 13 00:00-00:10` |

Column names are flexible (`ep`, `episode`; `in`/`out`; `start_time`…).
