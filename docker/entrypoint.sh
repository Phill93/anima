#!/bin/sh
# Anima-Entrypoint: Migrations + Static-Files vor dem eigentlichen Start.
# (web/worker/beat dürfen parallel starten: migrate/collectstatic sind idempotent.)
set -e

echo "[anima] Migrations anwenden..."
python manage.py migrate --noinput

echo "[anima] collectstatic..."
python manage.py collectstatic --noinput --clear

# CMD übergeben (gunicorn / celery worker / celery beat)
exec "$@"
