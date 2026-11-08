# 3-minute walkthrough video: script

Record with Loom or QuickTime (screen + mic). Have the app open at `localhost:8000` with the **real input pack already run once** (so the LLM cache makes it instant), plus a terminal.

| Time | Screen | Say (in your own words) |
|---|---|---|
| 0:00–0:15 | Home page | "I picked Problem 1. Today an editor watches every episode to find promos, and Kuku ships shows every week. This tool reads the screenplays instead and hands editors exact cut points." |
| 0:15–0:35 | Drop the input pack folder or zip, add my manual promos CSV, click **Find promos** | "It takes a folder, sub-folders, PDFs or a zip in any layout. It parses every timestamped line, then scores every 20–60 second window that starts and ends on a whole line." |
| 0:35–1:10 | **Ranked promos**, click #1, phone preview, cut points, Copy | "Each promo opens on a hook in the first 3 seconds, the pink line, and cuts on a cliffhanger, the teal line. Here's the episode, IN/OUT in timecode, and one line on why it works. The score breakdown shows exactly why it ranked here." |
| 1:10–1:30 | **Posting order** | "Ranking isn't posting. It leads with spoiler-safe early-episode hooks and alternates tropes so we learn which angle converts." |
| 1:30–2:00 | **Vs. your picks** | "Before running it I picked promos by hand. It found X of my Y. Here's each one side by side with the overlap and the seconds of difference, and for each miss, the reason: too long, stitched, or out-ranked because its hook is visual." |
| 2:00–2:20 | **Quality check** | "Where it picks badly: visual-only beats, sarcasm, callbacks. Every promo carries specific warning flags, so the editor knows what to check." |
| 2:20–2:40 | Terminal: `python -m promo_engine run -i data/input --llm-key <other key>` | "It works with no API key. To use any model, I paste one key: the prefix picks the provider and the model is discovered automatically. A stronger model is one key away, with no code change." |
| 2:40–3:00 | **Export**, open the EDL in Premiere/Resolve (or show the cut sheet) | "Editors import the EDL and every promo is already on a timeline. It costs about a cent per show with an LLM, and nothing without one. Thanks." |

Tips: zoom the browser to 110%, hide bookmarks, do one dry run, and keep it under 3:00.
