# docs/adr/README.md
# Architecture Decision Records

This directory contains ADRs (Architecture Decision Records) for the SatQuery AI P1 platform.
Each ADR documents a significant architectural or technical decision: the context, the decision made,
and its consequences.

## Index

| ADR | Title | Status |
|---|---|---|
| [ADR-0001](ADR-0001-monorepo-layout.md) | Python Monorepo with Flat Package Layout | Accepted |
| [ADR-0002](ADR-0002-fastapi-framework.md) | FastAPI as the HTTP Service Framework | Accepted |
| [ADR-0003](ADR-0003-rbac-design.md) | Role-Based Access Control (RBAC) Design | Accepted |
| [ADR-0004](ADR-0004-jwt-algorithm-strategy.md) | JWT Algorithm Strategy — HS256 (Dev) / RS256 (Prod) | Accepted |
| [ADR-0005](ADR-0005-opentelemetry-observability.md) | OpenTelemetry for Distributed Tracing and Structured Logging | Accepted |
| [ADR-0006](ADR-0006-internal-client-resilience.md) | Internal Service-to-Service Client with Resilience Patterns | Accepted |

## Format

Each ADR follows this template:
- **Status**: Proposed / Accepted / Deprecated / Superseded
- **Context**: What is the problem or situation?
- **Decision**: What was decided?
- **Consequences**: What are the trade-offs?
- **Alternatives Considered**: What else was evaluated and why was it rejected?
