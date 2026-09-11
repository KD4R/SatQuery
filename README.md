# SatQuery AI

> **Natural-language satellite intelligence platform** — query, analyze, and monitor Earth Observation data through a conversational AI interface.

---

## Monorepo Structure

```
SatQuery-1/
├── apps/
│   └── web/                    # P5 — Next.js frontend
├── services/
│   ├── gateway/                # P1 — API Gateway / BFF
│   ├── mission/                # P1 — Mission & AOI lifecycle
│   ├── agent/                  # P2 — LLM Agent orchestration
│   ├── inference/              # P3 — ML model inference
│   ├── eo-data/                # P4 — EO data ingestion (Bhoonidhi/STAC)
│   ├── geo/                    # P4 — Geospatial processing
│   ├── monitoring/             # Monitoring service
│   ├── reporting/              # Reporting service
│   └── notifications/          # Notifications service
├── packages/
│   ├── contracts/              # P1 — Canonical API & event schemas
│   ├── auth/                   # P1 — JWT/RBAC helpers
│   └── shared/                 # P1 — Internal client, utilities
├── ml/                         # P3 — Model training & evaluation
├── data/                       # P4 — Data pipelines & fixtures
├── infrastructure/             # P6 — Docker, monitoring, release
├── docs/
│   ├── architecture/adr/       # Architecture Decision Records
│   ├── api/                    # API reference
│   └── security/               # Security policies
└── tests/
    ├── contracts/              # Contract compatibility tests
    ├── integration/            # Cross-service integration tests
    ├── e2e/                    # End-to-end tests
    ├── security/               # Security tests
    ├── performance/            # Performance benchmarks
    └── chaos/                  # Chaos / resilience tests
```

---

## Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd SatQuery-1

# 2. Create & activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run all tests
PYTHONPATH=. pytest

# 5. Run Gateway locally
PYTHONPATH=. uvicorn services.gateway.implementation:app --reload --port 8000

# 6. Run Mission service locally
PYTHONPATH=. uvicorn services.mission.implementation:app --reload --port 8001
```

---

## APIs

| Service | Endpoint | Description |
|---------|----------|-------------|
| Gateway | `GET /api/v1/health` | Health check |
| Mission | `GET /api/v1/health` | Health check |
| Mission | `POST /api/v1/missions` | Create a mission *(P1-06)* |
| Mission | `GET /api/v1/missions/{id}` | Get a mission *(P1-06)* |
| Mission | `POST /api/v1/aois` | Create an AOI *(P1-06)* |
| Gateway | `WS /ws/v1/missions/{id}` | Real-time status stream *(P1-08)* |

---

## CI / CD

| Trigger | Pipeline | What runs |
|---------|----------|-----------|
| Every push / PR | `ci.yml` | lint → unit → integration → contract → security scan |
| Merge to `main` | `cd.yml` | Auto-tag + GitHub Release |
| Every PR | `pr-validation.yml` | Branch name + Conventional Commit title check |

---

## Team Ownership

| Role | Owner | Scope |
|------|-------|-------|
| P1 — Tech Lead | Backend | Gateway, Mission, shared packages, CI contracts |
| P2 — Agent | Backend | Agent service, LLM orchestration, evals |
| P3 — ML | ML Eng | Inference service, model training |
| P4 — EO Data | Backend | EO data ingestion, geo processing |
| P5 — Frontend | Frontend | Web app, TypeScript client |
| P6 — DevOps | DevOps | Docker, monitoring, release pipelines |

See [CONTRIBUTING.md](./CONTRIBUTING.md) for branching, commit conventions, and PR checklist.

---

## License

Proprietary — SatQuery AI. All rights reserved.