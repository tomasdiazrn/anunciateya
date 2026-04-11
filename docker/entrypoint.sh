#!/bin/sh
set -e
if [ "$1" = "gunicorn" ]; then
  shift
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    "$@"
else
  exec "$@"
fi
