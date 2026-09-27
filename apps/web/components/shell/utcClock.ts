/** Formats a Date as "HH:MM:SS" in UTC — shared by the top bar and the
 * page-bottom telemetry. */
export function utcClock(d: Date): string {
  const p = (n: number) => n.toString().padStart(2, "0");
  return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`;
}
