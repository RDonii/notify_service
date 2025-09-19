FROM python:3.13-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 10001 -ms /bin/bash appuser
WORKDIR /app

COPY pyproject.toml /app/
COPY app /app/app
COPY .docker/gunicorn.conf.py /app/.docker/gunicorn.conf.py

RUN pip install --no-cache-dir .

USER appuser
EXPOSE 8000

CMD ["gunicorn", "-c", ".docker/gunicorn.conf.py", "app.main:create_app"]
