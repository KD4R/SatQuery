# Remaining Task List (Per Person)

This is the comprehensive checklist of all remaining or partially completed issues across the 6 engineering tracks that need to be finished to achieve end-to-end production readiness.

### P1: Siddharth (Tech Lead + Backend Architect)
- [x] **P1-03** OAuth2/OIDC JWT verification foundation (Requires live IDP integration)
- [x] **P1-04** RBAC and tenant isolation (Requires deep enforcement on database reads)
- [x] **P1-07** Mission run/job lifecycle bridge
- [x] **P1-08** Mission WebSocket status stream (Currently a skeleton)
- [x] **P1-09** Audit trail and trace metadata
- [x] **P1-10** Shared internal client and error mapping
- [x] **P1-11** Service-to-service identities and scopes
- [x] **P1-12** Idempotency and duplicate execution controls (Needs robust cache implementation)
- [x] **P1-15** Mission ↔ Agent integration (Crucial: Wire gateway to LangGraph)
- [x] **P1-16** Generated frontend client verification

### P2: Agent Engineer (LangGraph / Orchestration)
- [ ] **P2-01** Agent service skeleton and MissionState (Needs actual LangGraph loop)
- [ ] **P2-02** Input sanitizer and intent validator
- [ ] **P2-03** Intent extraction and mission planning
- [ ] **P2-04** Async agent execute endpoint and run orchestration
- [ ] **P2-05** Versioned tool registry and schemas
- [ ] **P2-06** Permission-aware tool executor and budgets
- [ ] **P2-07** Observation search and asset selection tools (Crucial: Integrate with P4)
- [ ] **P2-08** Temporal planning and previous/current selection
- [ ] **P2-09** Adaptive sensor arbitration
- [ ] **P2-10** Evidence object / graph builder
- [ ] **P2-11** Confidence and uncertainty gate
- [ ] **P2-12** Sensor disagreement analysis
- [ ] **P2-13** Autonomous evidence acquisition loop
- [ ] **P2-14** Evidence-only output synthesizer and WHY explanation
- [ ] **P2-15** Prompt/evaluation harness and agent regression
- [ ] **P2-16** Agent observability and tool-call audit
- [ ] **P2-17** Agent failure/recovery policies
- [ ] **P2-18** Agent release hardening and pinned demo profile

### P3: Srushti (ML / Computer Vision Engineer)
- [ ] **P3-05** Temporal semantic change-detection pipeline (Blocked by P4)
- [ ] **P3-06** Cross-modal optical-SAR fusion (Evaluating if strictly required)
- [ ] **P3-12** Infrastructure intersection output adapter
- [ ] **P3-13** Flood composite analysis pipeline
- [ ] **P3-16** Inference observability and trace propagation
- [ ] **P3-17** Model/data provenance manifest
- [ ] **P3-18** Pinned inference release profile

### P4: Kavin (Geospatial / Data Engineer)
- [ ] **P4-04** STAC adapter (Needs live integration)
- [ ] **P4-05** Bhoonidhi adapter (Needs live integration)
- [ ] **P4-07** Spatial/temporal observation search
- [ ] **P4-08** Asset resolver
- [ ] **P4-09** Secure asset retrieval and content validation
- [ ] **P4-12** AOI clipping and windowed processing
- [ ] **P4-13** COG generation and overviews
- [ ] **P4-15** TiTiler integration (Crucial for P5 map rendering)
- [ ] **P4-18** Monitoring observation selection support
- [ ] **P4-19** EO data quality scoring/enrichment
- [ ] **P4-20** Pinned EO/Geo fixture pack and release hardening

### P5: Atharv (Frontend / Geospatial UX Engineer)
- [ ] **P5-01** Next.js application shell and design system
- [ ] **P5-02** Generated API client integration
- [ ] **P5-03** Mission console query and planning UX
- [ ] **P5-04** Mission status and run timeline
- [ ] **P5-05** MapLibre map workspace
- [ ] **P5-06** AOI draw/edit and validation UX
- [ ] **P5-07** Observation and before/after comparison
- [ ] **P5-08** Change polygons, masks and confidence visualization
- [ ] **P5-09** WHY? evidence panel
- [ ] **P5-10** Sensor arbitration and disagreement UI
- [ ] **P5-11** Confidence/uncertainty and human-in-loop UX
- [ ] **P5-12** Mission memory and temporal history
- [ ] **P5-13** Persistent monitoring mission screen
- [ ] **P5-14** Report generation and report view
- [ ] **P5-15** Admin, security and accessibility UX
- [ ] **P5-16** Frontend performance and error boundaries
- [ ] **P5-17** E2E UX hardening and deterministic demo mode

### P6: Swarali (Platform / DevOps + QA)
- [ ] **P6-01** Docker Compose local integration environment (Needs wiring for all 6 services)
- [ ] **P6-06** OpenTelemetry collector and structured logging
- [ ] **P6-07** Prometheus metrics and Grafana dashboards
- [ ] **P6-08** Cross-service integration test suite (True E2E)
- [ ] **P6-09** Flagship flood E2E automation (Blocked by P5 UI)
- [ ] **P6-10** Performance/load test harness
- [ ] **P6-12** Failure injection and recovery tests
- [ ] **P6-14** Monitoring/report integration QA
- [ ] **P6-15** Release candidate, immutable images and rollback
- [ ] **P6-16** Two full demo rehearsals and operator runbook
- [ ] **P6-17** Final QA sign-off and release gate
