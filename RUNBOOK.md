# RUNBOOK: your personal manual

What to run, in which order, and how to deploy. Written for macOS (it also works on Linux and WSL).
Every command runs from the project root (`Kuku FM/kuku-promo-finder`).

---

## 0. One-time setup (10 min)

```bash
cd "~/Documents/Kuku FM/kuku-promo-finder"        # or wherever the folder is
python3 --version                                   # need 3.10+  (brew install python@3.12 if older)
node --version                                      # need 18+    (brew install node)

python3 -m venv .venv && source .venv/bin/activate  # isolated Python env (repeat `source …` in every new terminal)
pip install -r requirements-dev.txt
(cd frontend && npm ci)
cp .env.example .env                                 # optional: paste ONE LLM key into LLM_API_KEY
```

Free keys (pick one): Gemini at <https://aistudio.google.com/apikey> (`AQ.…` or the older `AIza…`) or Groq at <https://console.groq.com/keys> (`gsk_…`).
Check it with `python -m promo_engine llm-check`, which prints the detected provider and model and makes one test call.

---

## 1. Run order (first time)

| Step | Command | What it proves / produces |
|---:|---|---|
| 1 | `python -m pytest` | 123 tests pass (≈10 s; 3 of them run on the real pack in `data/input`) |
| 2 | `python scripts/make_sample_data.py` | Rebuilds the synthetic sample show (already committed, so this is optional) |
| 3 | `make run-sample` | Promos on the sample + comparison → `outputs/raw_outputs_sample/` |
| 4 | The **input pack** is already in `data/input/I Married a Broken Soldier. He was a Duke/`. For another show, drop its folder/zip/PDFs into `data/input/` (one show at a time) or point `-i` at it anywhere | |
| 5 | `python -m promo_engine parse -i data/input -v 5` | **Check the parse first**: episode count, % timestamped, first 5 beats per episode. If something looks wrong, see §8. |
| 6 | `python -m promo_engine run -i data/input --no-llm -o outputs/check_rules` | Rules-only run. Open `outputs/check_rules/report.html` in a browser. |
| 7 | Write your manual promos in `data/manual_promos/my_manual_promos.csv` (copy the template) | Do this **before** looking at the tool's output, so the comparison is fair |
| 8 | `bash scripts/run_full_pack.sh` | **The raw-outputs deliverable** → `outputs/raw_outputs_full_pack/` (main run with LLM if a key is set, rules-only, 3 platform presets, parse log) and regenerates `METRICS.md` with the real comparison |
| 9 | `python -m promo_engine learn -i data/input -m data/manual_promos/my_manual_promos.csv` | Optional: fits the weights to your picks → `config/learned_weights.yaml`, used automatically by later runs. Re-run step 8 to see whether recall improves. Delete the file to undo. |
| 10 | `python scripts/generate_metrics.py --input data/input --manual data/manual_promos/my_manual_promos.csv` | Full `METRICS.md` (tests + ablations + real-pack section) |
| 11 | `python scripts/build_solution_doc.py` | Rebuilds `docs/Solution_Doc.pdf` (2 pages) with the real numbers from step 8. **Edit `docs/solution_doc.md` first** (your name, your AI-tool notes). |
| 12 | `bash scripts/render_diagrams.sh` | Only if you edited `docs/graphics/*.mmd` (needs `npm i -g @mermaid-js/mermaid-cli`) |

Makefile shortcuts: `make help`, `make test`, `make run-sample`, `make run`, `make compare MANUAL=…`, `make learn`, `make metrics`, `make doc-pdf`.

---

## 2. Command-line reference

```bash
python -m promo_engine run -i <folder|zip|file> [options]
  -m, --manual FILE        compare with your manual promos (csv/tsv/json/xlsx/txt)
  -o, --out DIR            output folder (default outputs/run_<timestamp>)
  --platform any|tiktok|reels|shorts
  --top-k N                max promos (default 30)
  --title "Show name"
  --no-llm                 rules only even if a key is set
  --llm-key KEY            one-off key (overrides .env)
  --llm-model ID           force a model
  --config my.yaml         override any value in config/default.yaml
  --with-timeline          include every parsed beat in promos.json
python -m promo_engine parse -i <input> [-v N] [--json timeline.json]
python -m promo_engine learn -i <input> -m <manual> [--dry-run]
python -m promo_engine llm-check [--key KEY]
python -m promo_engine serve [--port 8000]
```

Tuning without code: `config/default.yaml` holds the weights, lengths, top-k, per-episode cap, minimum score, montages and LLM batch size. `config/lexicons.yaml` holds the cue words for hooks, cliffhangers, tropes and context. If the show uses vocabulary the lexicon misses (e.g. werewolf "Alpha", "Luna"), add it there.

---

## 3. Web app on your laptop

**Development (hot reload, two terminals or `make dev`):**
```bash
make api      # FastAPI on :8000
make ui       # Vite on http://localhost:5173 (proxies /api to :8000)
```

**Production-like (one process):**
```bash
(cd frontend && npm run build)
python -m uvicorn backend.app:app --port 8000   # open http://localhost:8000
```
Locally the UI can also read `data/input` directly ("Or read a folder on the server"). This has no upload limit.

---

## 4. Docker

```bash
docker compose up --build            # http://localhost:8000
```
- `data/input` is mounted **read-only** into the container. Drop the pack there and type `data/input` in the UI.
- `outputs/`, `config/` and `data/feedback/` are mounted, so runs, tuning and feedback persist on your disk.
- `.env` is read automatically (your LLM key).
- Fully local LLM: `docker compose --profile local-llm up --build`, then `docker compose exec ollama ollama pull llama3.1` and set `LLM_API_KEY=ollama` and `LLM_BASE_URL=http://ollama:11434/v1` in `.env`.

Plain Docker: `docker build -t kuku-promo-finder . && docker run -p 8000:8000 --env-file .env -v "$PWD/data/input:/app/data/input:ro" kuku-promo-finder`.

---

## 5. Deploy to Vercel (free), the prototype link

`vercel.json` is ready: it builds the React UI into static files and runs `api/index.py` (FastAPI) as a Python function.

**Option A: through GitHub (recommended)**
1. Create a GitHub repo and push (see §6). Make it **private** if it will contain any Kuku outputs.
2. On <https://vercel.com/new>, import the repo. Framework preset: **Other**. Leave the build settings empty, since `vercel.json` sets them.
3. *Settings ▸ Environment Variables*: add `LLM_API_KEY` (optional).
4. Deploy, then open `https://<project>.vercel.app/api/health`. It should show `"ok": true`.
5. Open the site and click **Try the sample show**.

**Option B: CLI**
```bash
npm i -g vercel
vercel login
vercel              # preview deploy (answer the prompts; root = this folder)
vercel env add LLM_API_KEY
vercel --prod       # production URL
```

Vercel limits on the free plan: 4 MB uploads (**zip the pack**), 60 s per request, no persistent disk (exports are generated in the browser's session). For the full 50-episode pack with an LLM, run locally or in Docker and share the generated `report.html`.
The input pack is excluded from the deployment by `.vercelignore`.

Other free hosts: the Docker image runs unchanged on **Hugging Face Spaces** (Docker SDK, port 8000 → set `app_port: 8000`), Render or Railway.

---

## 6. Git / GitHub

```bash
git init && git add . && git commit -m "Kuku promo finder"
gh repo create kuku-promo-finder --private --source=. --push   # or create it on github.com and `git remote add origin …`
```
`.gitignore` already excludes `data/input/`, `.env`, `node_modules`, caches and run folders.
`outputs/raw_outputs_full_pack/` is **also ignored** because it contains confidential transcript excerpts. Submit it through the form (zip and upload to Drive with link sharing), or force-add it in a private repo: `git add -f outputs/raw_outputs_full_pack`.

---

## 7. Interview / demo day ("run it on a new input")

1. `source .venv/bin/activate && python -m pytest -q` (sanity check, 5 s).
2. Put the new show in `data/input_new/` (any format).
3. `python -m promo_engine parse -i data/input_new -v 3` to show it understood the format.
4. `python -m promo_engine run -i data/input_new --no-llm -o outputs/demo_rules` to get results in seconds.
5. If they give you a stronger model's key: `python -m promo_engine run -i data/input_new --llm-key <their key> -o outputs/demo_llm`. **No code change**: the prefix picks the provider. For a custom gateway: `LLM_BASE_URL=https://their-gateway/v1 LLM_API_KEY=... LLM_MODEL=... python -m promo_engine run …`.
6. Open `outputs/demo_llm/report.html`, or the web app → **Vs. your picks** if they bring their own promos.
7. Talk through one failure from the **Quality check** tab.

---

## 8. Fallback keys and other guardrails

```bash
# .env — the second key is used automatically if the first fails (invalid, quota, outage)
LLM_API_KEY=AIza...,gsk_...
# or
LLM_FALLBACK_API_KEYS=gsk_...,sk-or-...
```
Other guardrails need no setup: built-in config if the YAML breaks, per-episode and per-stage isolation, a circuit breaker and time budget for the LLM, min-score relaxation, and per-file export isolation. Full list with tests: `docs/robustness.md`. After editing `config/*.yaml`, run `python scripts/sync_defaults.py` so the built-in copy matches (a test reminds you).

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `parse` shows the wrong episode count | The parser looks for `EPISODE n` / `Ep n` / `S01E0n` / `EPISODE NUMBER: Episode n` lines, then file names. Rename files `Ep_01.txt`… or add headers. Check the warnings: header/file-name conflicts and ignored untimed files are listed. |
| Run finished but says "degraded stages" | One stage hit a bug and was skipped with a fallback. The warning names it; the promos are still valid. Report the message. |
| Low "timestamped" % | Lines lack timestamps in a format the parser knows. Run `parse -v 10`, look at the raw lines, and add the pattern to `TC_TOKEN` in `promo_engine/timecode.py` (and a test in `tests/test_timecode.py`). |
| Speakers missing (`dialogue_with_speaker` low in METRICS) | Names may be in an unusual style. See `LABEL_RE` / `CLASSIC_NAME_RE` in `ingest/parser.py`. |
| An obvious hook word isn't detected | Add it to `config/lexicons.yaml → hook → <category> → patterns`. |
| `LLM … HTTP 429` | Free-tier rate limit. The run continues on rules. Set `llm.max_concurrency: 1` in a config override, or re-run (the cache keeps finished batches). |
| `LLM … HTTP 404 model` | Set `LLM_MODEL` explicitly, or let discovery pick one by removing it. |
| `ModuleNotFoundError: promo_engine` | Run from the project root, or `pip install -e .`. |
| The UI shows an old run | It remembers the last run in the browser. Run again, or clear site data. |
| Vercel 413 | Zip the folder (< 4 MB) or use Docker. |

---

## 10. File map: what to open when

| You want to… | Open |
|---|---|
| Change weights, lengths, top-k | `config/default.yaml` |
| Add hook / cliffhanger words | `config/lexicons.yaml` |
| Understand the parse | `promo_engine/ingest/parser.py` |
| Understand a score | `promo_engine/generate/candidates.py` (features), `rank/scorer.py` |
| Change the LLM prompt | `promo_engine/llm/prompts.py` |
| Add a provider | `promo_engine/llm/base.py` → `PROVIDERS` + `KEY_PREFIXES` |
| Change exports | `promo_engine/export/` |
| Change the UI | `frontend/src/App.tsx`, `frontend/src/components/*`, `frontend/src/styles.css` |
| API endpoints | `backend/app.py` (interactive docs at `/docs` when running) |
