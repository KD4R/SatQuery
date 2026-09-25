# ─── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM public.ecr.aws/docker/library/python:3.10-slim AS builder

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

# P3. torch for the inference image only. Off by default, so the gateway, mission
# and agent images do not grow by the size of a deep-learning stack they never
# import. docker-compose sets INSTALL_ML=1 for `inference`.
#
# The CPU wheel, deliberately. The default Linux wheel bundles the CUDA runtime
# and is roughly ten times larger, for a 486K-parameter U-Net that infers a
# 512x512 chip in ~120 ms on two CPU threads (measured; see the P3 PR). A GPU
# would buy a tenth of a second at the cost of a multi-gigabyte image and a
# host driver requirement.
ARG INSTALL_ML=0

# torch is installed with --no-deps and its dependencies are resolved from PyPI
# first. The PyTorch CPU index mirrors torch's pure-Python dependencies, but its
# typing-extensions wheel has shipped a broken Name field ("typing_extensions"),
# so pip discards it, falls back to the sdist, and the build-isolation subprocess
# then fails to find flit_core on an index that only carries PyTorch packages.
# If a future torch version adds a dependency, add it to this list — the
# inference healthcheck fails visibly on an unimportable torch, so a stale list
# cannot ship silently.
RUN if [ "$INSTALL_ML" = "1" ]; then \
        pip install --no-cache-dir --prefix=/install \
            "filelock" "typing-extensions>=4.10" "sympy>=1.13.3" \
            "networkx>=2.5.1" "jinja2" "fsspec" && \
        pip install --no-cache-dir --prefix=/install \
            --index-url https://download.pytorch.org/whl/cpu --no-deps "torch>=2.4"; \
    fi

# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM public.ecr.aws/docker/library/python:3.10-slim AS runtime

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

# Model manifests (checksums, architecture, calibration). A few KB. The weights
# themselves are not in the image; they are mounted or fetched by checksum --
# see infrastructure/models/README.md and ml/scripts/fetch_model.py.
COPY infrastructure/models/ ./infrastructure/models/

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
