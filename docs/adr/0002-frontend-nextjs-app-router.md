# ADR 0002: Frontend Architecture with Next.js App Router

## Status
Accepted

## Context
SatQuery AI requires a robust frontend application that provides a unified control plane for intelligence operators to query, track, and monitor mission status. We need to decide on the structural framework for the frontend that accommodates:
- Geospatial mapping interactions (e.g., MapLibre, PMTiles).
- Real-time status updates (via WebSockets or polling).
- Complex application state management.
- Integration with the canonical Gateway OpenAPI layer.
- Long-term maintainability inside the monorepo architecture.

## Decision
We have decided to adopt **Next.js with the App Router** paradigm, contained within a dedicated `apps/web/` workspace in the monorepo structure. 
1. **Framework:** Next.js (App Router) provides a strong opinion on server/client boundaries, allowing us to build server-side rendered (SSR) or statically generated pages when needed, while delegating complex interactive state (like the MapLibre view) to client components.
2. **API Communication:** All communication between the frontend and the Python backend services must strictly go through the API Gateway (defined via `NEXT_PUBLIC_GATEWAY_URL`), using the generated TypeScript client (`packages/contracts/generated/ts`). Direct service-to-service communication from the frontend is strictly prohibited.
3. **Monorepo Placement:** The frontend is placed under `apps/web/` instead of a top-level `Frontend/` folder to adhere to standard modern monorepo patterns.

## Consequences
- **Positive:** Standardized project structure that aligns with modern frontend tooling. Strong TypeScript support via OpenAPI generation. Clear separation of frontend view layers from backend business logic.
- **Positive:** Simplifies integration testing as the frontend can be deployed independently or alongside the Gateway.
- **Negative:** Requires team familiarity with React Server Components (RSC) and the App Router model to avoid hydration issues when blending dynamic mapping components with server-rendered shells.
