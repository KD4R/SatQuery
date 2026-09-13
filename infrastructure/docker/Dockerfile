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

WORKDIR /app

# Copy application code — monorepo structure
COPY packages/ ./packages/
COPY services/ ./services/
COPY apps/api/ ./apps/api/
COPY ml/ ./ml/
COPY data/ ./data/
COPY tests/ ./tests/
COPY .importlinter .
COPY pyproject.toml .
COPY setup.cfg .

# Ownership
RUN chown -R satquery:satquery /app

USER satquery

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default: run the API gateway
CMD ["uvicorn", "services.gateway.implementation:app", "--host", "0.0.0.0", "--port", "8000"]
