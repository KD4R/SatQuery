"use client";

/**
 * Shared chrome for every route except the console (P5-01).
 *
 * The console owns its whole viewport and has its own telemetry bands, so it does
 * not use this. Everything else — mission memory, monitoring, report, admin — gets
 * the same two hairline bands and the same nav, so moving between them feels like
 * moving inside one instrument rather than between pages.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Label, StatusChip } from "../system/primitives";
import { demoModeEnabled } from "../../lib/api/source";

const NAV: { href: string; label: string }[] = [
  { href: "/console", label: "Console" },
  { href: "/missions", label: "Missions" },
  { href: "/monitoring", label: "Monitoring" },
  { href: "/admin", label: "Admin" },
];

export function RouteChrome({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const demo = demoModeEnabled();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <header>
        <div className="band">
          <Link href="/" className="row" style={{ gap: 12 }}>
            <Label>SatQuery</Label>
          </Link>
          <div className="band-spacer" />
          <span
            className="heading"
            style={{ fontSize: 13, letterSpacing: "0.22em", fontWeight: 700 }}
          >
            SATQUERY
          </span>
          <div className="band-spacer" />
          <div className="row" style={{ gap: 8 }}>
            {demo ? <StatusChip tone="fixture">Demo fixtures</StatusChip> : null}
            {actions}
          </div>
        </div>

        <nav className="band" style={{ height: 28 }} aria-label="Sections">
          <div className="row" style={{ gap: 2 }}>
            {NAV.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="label"
                  aria-current={active ? "page" : undefined}
                  style={{
                    padding: "5px 10px",
                    color: active ? "var(--ink)" : "var(--ink-faint)",
                    borderBottom: active
                      ? "1px solid var(--signal)"
                      : "1px solid transparent",
                  }}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
          <div className="band-spacer" />
          <Label faint>{title}</Label>
        </nav>
      </header>

      <main
        id="mission-main"
        tabIndex={-1}
        style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto" }}
      >
        {children}
      </main>
    </div>
  );
}
