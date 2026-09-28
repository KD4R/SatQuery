/**
 * The route table for the whole app: one place that says where things live.
 *
 * Why this exists: the landing page's "Console" links used to be string literals
 * pointing at /console, while the mission console the team was actually building
 * lived at /dashboard. Nothing connected the two, so the landing page kept opening
 * a superseded screen and the real one was reachable only by typing its URL. Every
 * in-app link now goes through ROUTES, and `lib/nav.test.ts` fails if a link
 * targets a path that is neither a real page nor a declared redirect.
 *
 * This module must stay dependency-free: next.config.ts imports LEGACY_REDIRECTS.
 */

export const ROUTES = {
  home: "/",
  /** The canonical mission console. The landing page's Console CTA lands here. */
  console: "/dashboard",
  monitoring: "/dashboard/monitoring",
  history: "/dashboard/history",
  reports: "/dashboard/reports",
  evidence: "/dashboard/evidence",
  alerts: "/dashboard/alerts",
  settings: "/dashboard/settings",
  admin: "/dashboard/admin",
} as const;

export function reportRoute(missionId: string): string {
  return `${ROUTES.reports}/${encodeURIComponent(missionId)}`;
}

export interface LegacyRedirect {
  source: string;
  destination: string;
}

/**
 * Paths that used to serve a second, parallel copy of a screen. They redirect to
 * the canonical route instead of rendering, so a bookmark or an old link still
 * lands somewhere correct and there is exactly one implementation of each screen.
 *
 * Temporary (307) rather than permanent (308): browsers cache a 308 for as long
 * as they like, and a mistaken permanent redirect cannot be recalled. Flip
 * `permanent` once the layout has stopped moving.
 */
export const LEGACY_REDIRECTS: readonly LegacyRedirect[] = [
  { source: "/console", destination: ROUTES.console },
  { source: "/monitoring", destination: ROUTES.monitoring },
  { source: "/missions", destination: ROUTES.history },
  { source: "/missions/:id/report", destination: `${ROUTES.reports}/:id` },
  { source: "/admin", destination: ROUTES.admin },
  // The dashboard's own retired pages: the map merged into Mission, and the
  // secondary-dashboard draft was a placeholder surface, not a route to keep.
  { source: "/dashboard/map", destination: ROUTES.console },
  { source: "/dashboard/preview", destination: ROUTES.console },
];
