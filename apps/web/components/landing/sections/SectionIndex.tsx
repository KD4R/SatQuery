/** "01 ── MEASURED, NOT CLAIMED": the running section number and name. */
export function SectionIndex({ n, label }: { n: number; label: string }) {
  return (
    <span className="sq-index">
      <b>{String(n).padStart(2, "0")}</b>
      <i aria-hidden="true" />
      {label}
    </span>
  );
}
