# ─── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /build

# System deps for rasterio, shapely, psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.10-slim AS runtime

LABEL maintainer="SatQuery AI — P6 DevOps"
LABEL description="SatQuery AI API + Services (monolith with import-linter boundaries)"

# Runtime system deps — install from -dev packages then clean up headers.
# This avoids hardcoding library version numbers (libgdal32, libgeos-c1v5, etc.)
# which differ between Debian releases.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages
COPY --from=builder /install /usr/local

# Non-root user
RUN groupadd -r satquery && useradd -r -g satquery -d /app -s /sbin/nologin satquery

# Which ASGI app this image variant serves. The CD pipeline builds three
# immutable variants from this one Dockerfile:
#   satquery-api     -> services.gateway.implementation:app
#   satquery-mission -> services.mission.implementation:app
#   satquery-agent   -> services.agent.app.api.implementation:app
ARG APP_MODULE=services.gateway.implementation:app
ENV APP_MODULE=${APP_MODULE}

WORKDIR /app

# Copy application code — monorepo structure
COPY packages/ ./packages/
COPY services/ ./services/
COPY ml/ ./ml/
COPY data/ ./data/
COPY .importlinter .

# Runtime import alias for the hyphenated services/eo-data directory —
# Python auto-imports sitecustomize in every container process. Mirrors
# conftest.py's test-only finder; remove when the dir is renamed eo_data.
COPY infrastructure/docker/sitecustomize.py /usr/local/lib/python3.10/site-packages/sitecustomize.py
COPY pyproject.toml .
COPY setup.cfg .

# Ownership
RUN chown -R satquery:satquery /app

USER satquery

# Expose API port
EXPOSE 8000

# Health check — mode-aware: API containers answer the HTTP probe; Celery
# workers have no HTTP server, so fall back to a broker round-trip ping of
# their own node (default node name is celery@<hostname>). A worker that has
# crashed or lost the broker reports unhealthy instead of falsely green.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD sh -c "curl -sf http://localhost:8000/api/v1/health || celery -A services.celery_orchestrator inspect ping --destination celery@\$HOSTNAME --timeout 5 2>/dev/null | grep -q pong" || exit 1

# Default: run the API gateway. sh -c + exec keeps uvicorn as PID 1 so
# SIGTERM reaches it directly (fast, graceful container shutdown).
CMD ["sh", "-c", "exec uvicorn \"${APP_MODULE}\" --host 0.0.0.0 --port 8000"]
