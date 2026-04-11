# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

COPY . .

ARG BUILD_SECRET_KEY="build-only-collectstatic-key-not-used-in-runtime-50chars-min!!"
RUN SECRET_KEY="${BUILD_SECRET_KEY}" \
    ALLOWED_HOSTS=localhost \
    POSTGRES_DB=build \
    POSTGRES_USER=build \
    POSTGRES_PASSWORD=build \
    POSTGRES_HOST=127.0.0.1 \
    SECURE_SSL_REDIRECT=False \
    python manage.py collectstatic --noinput

RUN adduser --system --group --uid 1000 django \
    && chown -R django:django /app /entrypoint.sh

USER django

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn"]
