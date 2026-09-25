# SatQuery AI - Security Findings

## Executive Summary
The security architecture designed in the PRDs is robust and follows defense-in-depth principles (JWT Auth -> RBAC/Tenant -> Input/Geo Validation -> Policy/Tool Allowlist -> Agent/Services). The backend implementations of these security controls are mostly present, but they are bypassed at the integration layer.

## OWASP Top 10 Assessment

### A01 Broken Access Control
- **Finding:** The frontend completely bypasses access control by mocking responses using `setTimeout`.
- **Finding:** The `jwt.py` implementation correctly asserts `org_id` and `sub` claims, preventing IDOR/BOLA attacks.
- **Severity:** P0/Blocker (due to UI bypass).

### A02 Cryptographic Failures
- **Finding:** `packages/auth/jwt.py` correctly pins the signature algorithm to configuration rather than trusting the header.
- **Finding:** Local HS256 usage is correctly separated from production RS256 JWKS usage, reducing the chance of secret leakage.
- **Severity:** Pass.

### A03 Injection (Prompt & System)
- **Finding:** `services/agent/graph/orchestrator.py` correctly uses `sanitize_prompt(query)` before executing the LangGraph agent, mitigating basic prompt injection.
- **Finding:** Tool executions are governed by `ToolBudget` to prevent resource exhaustion and denial of wallet attacks.
- **Severity:** Pass.

### A04 Insecure Design
- **Finding:** The integration relies heavily on deterministic test fixtures and mock data. If the `SATQUERY_EXPLICIT_DEMO=false` flag is improperly configured, the system degrades to returning fabricated results, breaking the trust boundary.
- **Severity:** P1/High.

### Data / AI Safety Audit
- **Finding:** The LLM acts strictly as a "coordinator/synthesizer" and NOT as a source of factual claims. In `services/agent/nodes/synthesizer.py`, the AI strictly cites nodes from the `EvidenceGraph` (e.g. `inundation_area_sqkm`).
- **Finding:** Provenance tracing is actively implemented.
- **Severity:** Pass.
