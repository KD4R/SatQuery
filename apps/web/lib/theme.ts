export type Theme = "dark" | "light";

/**
 * One storage key, shared with the pre-hydration script in app/layout.tsx.
 *
 * The bootstrap script reads `satquery-theme` while this module used to read and
 * write a different key (`theme`), so a reload restored one theme while the toggle
 * icon believed another. The document attribute is the source of truth at read
 * time because the bootstrap has already resolved storage, cookie and the system
 * preference into it before React mounts.
 */
const KEY = "satquery-theme";

export function readTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  const attr = document.documentElement.dataset.theme;
  if (attr === "light" || attr === "dark") return attr;
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* storage can be blocked; fall through to the default */
  }
  return "dark";
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* a blocked store only costs persistence, not the theme */
  }
  document.cookie = `${KEY}=${theme}; path=/; max-age=31536000; SameSite=Lax`;
}
