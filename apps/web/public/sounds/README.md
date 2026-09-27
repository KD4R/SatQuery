# Intro sound

Put the landing page's opening sound here as `intro.mp3`.

- Played once, the first time a browser opens the site, while the SatQuery mark
  is in the middle of the screen (see `components/landing/introSound.ts`).
- Any length works; it is capped at 3.5 seconds and faded out.
- `intro.mp3` is gitignored: it stays on your machine and is never pushed. To
  ship a sound publicly, use one you have the rights to and remove that
  `.gitignore` line.
- Only use audio you have the right to ship (your own recording, or a clip whose
  licence allows use in a public website).

If no `intro.mp3` is present, a built-in synthesised sound is used instead.
