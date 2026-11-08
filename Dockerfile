# ---- 1) build the React UI ---------------------------------------------------
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2) Python API that also serves the built UI ------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY promo_engine ./promo_engine
COPY backend ./backend
COPY api ./api
COPY config ./config
COPY scripts ./scripts
COPY data/sample ./data/sample
COPY data/manual_promos ./data/manual_promos
COPY --from=web /web/dist ./frontend/dist
RUN mkdir -p data/input data/feedback outputs .cache \
 && useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT}"]
