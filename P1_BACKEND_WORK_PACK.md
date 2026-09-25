# P1: Backend & Gateway Work Package (Siddharth)

## Objective
Finalize the API boundaries, proxy routing, and real-time state propagation to ensure the frontend (P5) and Agent (P2) can communicate securely and without fallbacks.

## Tasks

### 1. Solidify Gateway Proxying
The frontend migration branch (`feat/p5-frontend-migration`) contains updates to `services/gateway/routers/proxy.py` to route frontend requests to the underlying internal microservices. 
- Review and finalize the proxy rules to ensure all generated OpenAPI client requests from P5 reach the correct P2/P3/P4 services.
- Ensure CORS and rate-limiting are appropriately configured for live frontend consumption.

### 2. Live WebSocket Status Stream
- The WebSocket implementation in `services/gateway/routers/missions_ws.py` currently falls back to a mock sequence if Redis is missing.
- **Action:** Ensure the WebSocket connects to the live Redis/Celery streams used by the P2 Agent. Broadcast granular step-by-step progress to the P5 UI so the user sees real-time agent thoughts.

### 3. Enforce End-to-End Security
- Ensure all endpoints hit by the P5 UI require and validate the JWT token properly using the `jwt.py` implementations.
- Verify that S2S (Service-to-Service) tokens are properly generated and passed down the trace (e.g., Gateway -> Mission -> Agent -> Inference).

### 4. Integration Support
- Support Atharv (P5) in integrating the generated API client.
- Ensure `ErrorResponse` schemas are cleanly propagated back to the frontend on actual failures (instead of silent 500s).
