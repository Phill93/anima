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
    PATH=/app/.venv/bin:$PATH

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

# Non-Root-User; /data = SQLite + ChromaDB + Static-Files
RUN useradd -m anima && mkdir -p /data && chown -R anima:anima /data /app
USER anima

EXPOSE 8000

# Healthchecks sind ein Deploy-Concern (pro-Service, in docker-compose.yml) —
# kein Image-Concern. Ein Image-Healthcheck würde von worker/beat geerbt werden
# und auf Port 8000 schlagen, wo kein HTTP-Server lauscht -> dauerhaft unhealthy.

# Migrate + collectstatic vor jedem Start; CMD pro Service (web/worker/beat).
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "anima.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
