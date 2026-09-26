"use client";

import Link from "next/link";

const LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#radar", label: "Why radar" },
  { href: "#validation", label: "Validation" },
  { href: "#honesty", label: "Evidence first" },
];

export function Nav({ scrolled }: { scrolled: boolean }) {
  return (
    <header className={`sq-nav${scrolled ? " is-scrolled" : ""}`}>
      <div className="sq-wrap sq-nav-inner">
        <a href="#top" className="sq-brand" aria-label="SatQuery, back to top">
          <span className="sq-brand-mark" aria-hidden="true" />
          SATQUERY
        </a>
        <nav className="sq-nav-links" aria-label="Sections">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href}>
              {l.label}
            </a>
          ))}
        </nav>
        <Link href="/console" className="sq-btn sq-btn-ghost sq-btn-sm">
          Open console
        </Link>
      </div>
    </header>
  );
}
