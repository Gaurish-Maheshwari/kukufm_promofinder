# outputs/ — raw outputs (required deliverable)

Every run writes one folder with unedited outputs:

| File | For whom | What |
|---|---|---|
| `promos_report.md` / `report.html` | Everyone | Ranked promos, posting plan, details, quality check, comparison |
| `editor_cut_sheet.csv` | Editors | Posting order, episode, source file, IN/OUT in SMPTE timecode (30 fps) with handles |
| `promos.edl` | Editors | CMX3600 EDL: import into Premiere / Resolve / Avid, every promo on one timeline |
| `markers.csv` | Editors | One marker per segment |
| `ffmpeg_cuts.sh` | Editors (optional) | Cuts raw previews if the episode videos exist |
| `promos.csv` | Analysts | One row per segment: hook, cliffhanger, why, tropes, flags |
| `promos.json` | Machines | Everything: transcripts, score breakdowns, metrics, comparison (`--with-timeline` adds every parsed beat) |
| `metrics.json` | QA | Brief compliance, diversity, runtime, LLM usage |
| `comparison_vs_manual.csv` | You | Your manual promos side by side with the tool's, with a diagnosis per miss |

## What is here

- `raw_outputs_sample/`: the synthetic sample show (rules only), compared against its manual promos.
- `raw_outputs_sample/platform_tiktok/`: the same show with the TikTok preset (20–35 s).
- `raw_outputs_sample/with_mock_llm_judge/`: the same show with the offline mock LLM judge, to show the re-rank path. A real key gives real judgements.

## The real input pack (do this before submitting)

```bash
bash scripts/run_full_pack.sh            # writes outputs/raw_outputs_full_pack/
```

This is the folder the brief asks for ("unedited outputs from running your solution on the full input pack").
Kuku's screenplays are confidential, so share it only through the submission form and do not commit it to a public repo
(`.gitignore` excludes it by default; remove the ignore line only if your repo is private).
