# Anima — Produktion (Gunicorn + Whitenoise, Celery in separaten Services)
#
# Build:  docker build -t anima .
# Run:    docker compose up -d (siehe docker-compose.yml)
#
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    # Sentence-Transformer-Modell (bge-m3, ~2 GB) im Data-Volume halten,
    # damit es nach einem Container-Rebuild nicht neu geladen wird.
    HF_HOME=/data/hf-cache

# uv (Version = lokale Entwicklungs-Umgebung, 2026-09)
RUN pip install --no-cache-dir uv==0.12.14

WORKDIR /app

# Projekt (App-Pakete + Lock-File). Dependency-Cache: pyproject/lock zuerst
# würde nicht helfen, da uv das Projekt-Paket selbst mitbaut — daher ein
# simpler, robuster COPY.
COPY . .

# Abhängigkeiten aus dem Lock installieren (ohne Dev-Gruppe:
# `uv sync` installiert standardmäßig nur die Haupt-Dependencies).
RUN uv sync --frozen

# Non-Root-User; /data = SQLite + ChromaDB + Static-Files + HF-Modell-Cache
RUN useradd -m anima && mkdir -p /data && chown -R anima:anima /data /app
USER anima

EXPOSE 8000

# Healthcheck ohne curl (slim-Image): Python-Stdlib reicht.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')" || exit 1

# Migrate + collectstatic vor jedem Start; CMD pro Service (web/worker/beat).
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "anima.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
