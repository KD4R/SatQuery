/**
 * The hero headline.
 *
 * Static-first: with JavaScript off, reduced motion, or a screenshot taken before
 * anything runs, it is three finished lines of type with "evidence" underlined. The
 * motion is a single pass that reads as signal -> processing -> information: a
 * one-pixel scan line travels down the block, each line is unmasked as the scan
 * reaches it, and the underline under "evidence" draws last. It runs once and stops.
 *
 * Pure CSS (see .sq-headline in space.css), so it plays from the server-rendered
 * HTML without waiting for hydration and can never leave the headline hidden.
 */

const line = (i: number) => ({ "--i": i }) as React.CSSProperties;

export function HeroHeadline() {
  return (
    <h1 className="sq-headline">
      <span className="sq-scan" aria-hidden="true" />
      <span className="sq-headline-line">
        <span style={line(0)}>Ask a question.</span>
      </span>
      <span className="sq-headline-line">
        <span style={line(1)}>Get an answer</span>
      </span>
      <span className="sq-headline-line sq-headline-line--quiet">
        <span style={line(2)}>
          with its <span className="sq-headline-mark">evidence</span>.
        </span>
      </span>
    </h1>
  );
}
