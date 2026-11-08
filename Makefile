# Kuku Promo Finder — common tasks. `make help` lists them.
PY ?= python3
INPUT ?= data/input
MANUAL ?= data/manual_promos/my_manual_promos.csv
OUT ?= outputs/run_latest

.PHONY: help setup sample test run run-sample compare learn dev api ui build serve metrics diagrams doc-pdf docker-build docker-up clean

help:            ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[1m%-13s\033[0m %s\n", $$1, $$2}'

setup:           ## install Python + frontend dependencies
	$(PY) -m pip install -r requirements-dev.txt
	cd frontend && npm ci

sample:          ## (re)generate the synthetic sample show in data/sample
	$(PY) scripts/make_sample_data.py

test:            ## run the test suite
	$(PY) -m pytest

run-sample:      ## find promos in the sample show and compare with its manual promos
	$(PY) -m promo_engine run -i data/sample/sample_show.zip -m data/sample/manual_promos_sample.csv -o outputs/raw_outputs_sample --title "The Maid Who Owns the Mansion"

run:             ## find promos in the real input pack (INPUT=data/input)
	$(PY) -m promo_engine run -i $(INPUT) -o $(OUT)

compare:         ## run + compare with your manual promos (MANUAL=...)
	$(PY) -m promo_engine run -i $(INPUT) -m $(MANUAL) -o $(OUT)

learn:           ## fit scoring weights to your manual promos
	$(PY) -m promo_engine learn -i $(INPUT) -m $(MANUAL)

api:             ## backend with auto-reload on :8000
	$(PY) -m uvicorn backend.app:app --reload --port 8000

ui:              ## frontend dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

dev:             ## backend + frontend together
	$(MAKE) -j2 api ui

build:           ## production build of the UI
	cd frontend && npm run build

serve: build     ## one process: API + built UI on :8000
	$(PY) -m uvicorn backend.app:app --host 0.0.0.0 --port 8000

metrics:         ## run tests + benchmarks and regenerate METRICS.md
	$(PY) scripts/generate_metrics.py

diagrams:        ## render docs/graphics/*.mmd to SVG + PNG
	bash scripts/render_diagrams.sh

doc-pdf:         ## build docs/Solution_Doc.pdf (2 pages)
	$(PY) scripts/build_solution_doc.py

docker-build:    ## build the Docker image
	docker build -t kuku-promo-finder .

docker-up:       ## run with docker compose on :8000
	docker compose up --build

clean:           ## remove caches and run folders
	rm -rf .cache outputs/runs .pytest_cache frontend/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
