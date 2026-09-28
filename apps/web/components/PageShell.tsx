"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import DashboardTopBar, { DASHBOARD_TABS } from "./DashboardTopBar";
import PageTelemetry from "./PageTelemetry";
import { ROUTES } from "../lib/nav";

/**
 * Sub-page shell for the dashboard family. One nav bar (DashboardTopBar:
 * brand + section chips + icon actions); the UTC/gateway/state telemetry is a
 * quiet subset at the bottom of the page.
 *
 * The active tab is the section whose href is the longest prefix of the pathname,
 * so /dashboard/reports/<mission> still lights "Reports". Passing the raw
 * pathname would match no tab on any nested route.
 */

export function activeSection(pathname: string): string {
  const match = DASHBOARD_TABS.filter(
    (t) => pathname === t.href || pathname.startsWith(`${t.href}/`),
  ).sort((a, b) => b.href.length - a.href.length)[0];
  return match?.href ?? ROUTES.console;
}

export default function PageShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    Object.values(ROUTES).forEach((path) => router.prefetch(path));
  }, [router]);

  return (
    <>
      <DashboardTopBar activeHref={activeSection(pathname)} />
      <div className="app-shell app-shell--flat">
        {/* #mission-main is the skip-link target declared in the root layout. */}
        <main className="main" id="mission-main" tabIndex={-1}>
          <div className="content">{children}</div>
          <PageTelemetry />
          <footer className="app-footer">
            <div>
              <b>SatQuery AI</b>
              <span>Evidence-first satellite intelligence</span>
            </div>
            <div>
              <span>Gateway-only browser access</span>
              <span>•</span>
              <span>Traceable outputs</span>
              <span>•</span>
              <span>Accessible UI</span>
            </div>
          </footer>
        </main>
      </div>
    </>
  );
}
