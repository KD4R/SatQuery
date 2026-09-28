"use client";

/**
 * Chrome for the section screens (mission memory, monitoring, report, admin).
 *
 * These screens used to draw their own two-band header with a nav that pointed at
 * the superseded /console. They now sit inside the dashboard shell — the same nav
 * bar, telemetry line and footer as the mission console — so moving between
 * Mission, Monitoring, History, Reports and Admin is one instrument, not two apps.
 *
 * `title` labels the screen for assistive tech (the visible heading belongs to the
 * screen itself); `actions` are screen-level status chips, right-aligned above the
 * content.
 */

import type { ReactNode } from "react";

import PageShell from "../PageShell";
import { demoModeEnabled } from "../../lib/api/source";
import { StatusChip } from "../system/primitives";

export function RouteChrome({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const demo = demoModeEnabled();

  return (
    <PageShell>
      <section aria-label={title}>
        {demo || actions ? (
          <div
            className="row"
            style={{ gap: 8, justifyContent: "flex-end", marginBottom: 8 }}
          >
            {demo ? <StatusChip tone="fixture">Demo fixtures</StatusChip> : null}
            {actions}
          </div>
        ) : null}
        {children}
      </section>
    </PageShell>
  );
}
