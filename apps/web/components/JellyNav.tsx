"use client";

/**
 * The dashboard's top nav: the JellyRadio segmented control carrying the
 * section tabs. Selecting a chip plays the jelly wobble and navigates
 * client-side; the radio always reflects the real route, so back/forward
 * and external links stay truthful. The active tab shows a small icon.
 */

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import JellyRadio from "./jelly/JellyRadio";
import type { DashboardTab } from "./DashboardTopBar";

export default function JellyNav({
  tabs,
  activeHref: activeHrefProp,
}: {
  tabs: DashboardTab[];
  /** Resolved active section when the host already knows it. */
  activeHref?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  // The chip row only navigates on click; the displayed selection follows the
  // route. Local state exists so the wobble target is the chip the user hit,
  // even before the route commit lands.
  const [pressed, setPressed] = useState<string | null>(null);

  const activeHref =
    activeHrefProp ??
    tabs.filter((t) => pathname === t.href || pathname.startsWith(t.href + "/"))
      .sort((a, b) => b.href.length - a.href.length)[0]?.href ??
    tabs[0].href;
  const selected = pressed ?? activeHref;

  const change = useCallback(
    (value: string) => {
      const tab = tabs.find((t) => t.href === value);
      if (!tab || value === activeHref) return;
      setPressed(value);
      router.push(value);
    },
    [tabs, activeHref, router],
  );

  // Route settled (or changed under us): drop the optimistic press.
  useEffect(() => {
    if (pressed && activeHref === pressed) setPressed(null);
  }, [pressed, activeHref]);

  return (
    <div className="jelly-nav">
      <JellyRadio
        items={tabs.map((t) => ({
          value: t.href,
          label: t.label,
          icon: t.icon ? <t.icon size={11} /> : undefined,
        }))}
        value={selected}
        onChange={(v) => change(v)}
        size="xs"
        gap={2}
        radius={8}
        swell={0.08}
        barge={3}
        shrink={0.03}
        jelly={0.8}
        bounce={0.22}
        stagger={16}
        stiffness={620}
        ariaLabel="Dashboard sections"
        className="jelly-nav-radio"
      />
    </div>
  );
}
