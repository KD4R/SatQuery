/**
 * Provenance of a value shown in the UI (P5-17).
 *
 * The rule this file exists to enforce: the operator must never be unable to tell
 * whether what is on screen came from the backend or from a demo fixture. Every
 * value that reaches a panel is wrapped, and every panel renders the badge.
 *
 * There is deliberately no `unwrap()` helper that discards the source. Reading the
 * data means reading `.value`, which keeps `.source` in view at the call site.
 */

export type DataSource = "gateway" | "fixture";

export interface Sourced<T> {
  value: T;
  source: DataSource;
  /** When the value was obtained, ISO-8601. Fixtures carry their pinned timestamp. */
  at: string;
  /** Correlation id from the backend, when there is one. */
  traceId?: string | null;
}

export function fromGateway<T>(
  value: T,
  traceId?: string | null,
  at: string = new Date().toISOString(),
): Sourced<T> {
  return { value, source: "gateway", at, traceId: traceId ?? null };
}

/**
 * Wrap a fixture value. `at` is required and must be a pinned constant -- a fixture
 * that stamps itself with the wall clock is not deterministic, and the demo has to
 * produce identical output on every run (P5-17).
 */
export function fromFixture<T>(value: T, at: string): Sourced<T> {
  return { value, source: "fixture", at, traceId: null };
}

export function isFixture<T>(s: Sourced<T>): boolean {
  return s.source === "fixture";
}

