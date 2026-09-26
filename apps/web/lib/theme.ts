export type Theme = 'dark' | 'light';

export function readTheme(): Theme {
  if (typeof window === 'undefined') return 'dark';
  return (localStorage.getItem('theme') as Theme) || 'dark';
}

export function applyTheme(theme: Theme) {
  if (typeof window === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}
