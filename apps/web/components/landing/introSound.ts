/**
 * The two-second opening sound, played once per browser -- the first time
 * someone opens the site -- while the SatQuery mark is in the middle.
 *
 * If apps/web/public/sounds/intro.mp3 exists, that file is played (capped at 3 s
 * and faded out). Otherwise a sound is synthesised with the Web Audio API: a low
 * pad swells in, a tone sweeps up like a signal locking on, and two soft pings
 * land (a radar echo) as the cube settles. About 2 seconds.
 *
 * Browsers only allow sound after the visitor has interacted with a page, and a
 * website cannot override that. So on a first visit where the browser holds the
 * sound, the intro shows "Click anywhere to enter" and waits: that click is what
 * lets the sound play, in sync with the cube. Where the browser already allows
 * sound, it simply plays. It is marked as played only once it has actually
 * started, so nobody hears it twice, and nobody who missed it loses it.
 */

const KEY = "sq-intro-sound-played";

/** Drop an audio file here (apps/web/public/sounds/intro.mp3) to replace the
 *  synthesised sound. Any length; it is capped at MAX_FILE_S and faded out. */
const SOUND_URL = "/sounds/intro.mp3";
const MAX_FILE_S = 3;

function alreadyPlayed(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return true; // storage blocked: stay quiet rather than risk playing every load
  }
}

function markPlayed() {
  try {
    localStorage.setItem(KEY, "1");
  } catch {
    /* ignore */
  }
}

function compose(ctx: AudioContext) {
  const t0 = ctx.currentTime + 0.02;
  const master = ctx.createGain();
  master.gain.value = 0.55;
  const comp = ctx.createDynamicsCompressor();
  master.connect(comp).connect(ctx.destination);

  // low pad: two detuned sines swelling in and fading out
  for (const f of [110, 110.9]) {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    o.frequency.value = f;
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime(0.14, t0 + 0.45);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + 2.0);
    o.connect(g).connect(master);
    o.start(t0);
    o.stop(t0 + 2.05);
  }

  // the lock-on sweep
  const sweep = ctx.createOscillator();
  const sg = ctx.createGain();
  const lp = ctx.createBiquadFilter();
  sweep.type = "triangle";
  sweep.frequency.setValueAtTime(220, t0 + 0.1);
  sweep.frequency.exponentialRampToValueAtTime(880, t0 + 1.15);
  lp.type = "lowpass";
  lp.frequency.value = 2400;
  sg.gain.setValueAtTime(0, t0 + 0.1);
  sg.gain.linearRampToValueAtTime(0.06, t0 + 0.6);
  sg.gain.exponentialRampToValueAtTime(0.0001, t0 + 1.25);
  sweep.connect(lp).connect(sg).connect(master);
  sweep.start(t0 + 0.1);
  sweep.stop(t0 + 1.3);

  // two pings: the pulse and its echo
  const ping = (at: number, freq: number, level: number) => {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    o.frequency.value = freq;
    g.gain.setValueAtTime(0, at);
    g.gain.linearRampToValueAtTime(level, at + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, at + 0.6);
    o.connect(g).connect(master);
    o.start(at);
    o.stop(at + 0.65);
  };
  ping(t0 + 1.2, 1318.5, 0.16);
  ping(t0 + 1.45, 1318.5, 0.06);
}

export interface IntroSound {
  /** True when the sound is still owed but the browser will only allow it after
   *  a click or key press -- the intro then waits for one ("click to enter"). */
  needsGesture: boolean;
  /** Start the sound. Call it synchronously inside the click/key handler. */
  play: () => void;
  /** Release the audio context (call when the intro is over). */
  stop: () => void;
}

const SILENT: IntroSound = {
  needsGesture: false,
  play: () => {},
  stop: () => {},
};

/**
 * Prepares the opening sound for this load. Silent (no-op) if this browser has
 * already heard it or cannot make sound at all.
 */
export function createIntroSound(): IntroSound {
  if (typeof window === "undefined" || alreadyPlayed()) return SILENT;
  const AC =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!AC) return SILENT;

  let ctx: AudioContext;
  try {
    ctx = new AC();
  } catch {
    return SILENT;
  }

  // If the project ships its own sound at public/sounds/intro.mp3, use it;
  // otherwise fall back to the synthesised one. Fetched and decoded now, while
  // the mark is on screen, so it is ready by the time the click comes.
  let file: AudioBuffer | null = null;
  const loaded: Promise<void> = fetch(SOUND_URL)
    .then((r) =>
      r.ok ? r.arrayBuffer() : Promise.reject(new Error("no file")),
    )
    .then((data) => ctx.decodeAudioData(data))
    .then((buf) => {
      file = buf;
    })
    .catch(() => undefined);
  // never hold the sound back more than this waiting for the file
  const loadedOrLate = () =>
    Promise.race([loaded, new Promise<void>((r) => setTimeout(r, 800))]);

  let done = false;
  const start = () => {
    if (done || ctx.state !== "running") return;
    done = true;
    let length = 2.0;
    if (file) {
      // play the file, capped and faded out so it never outstays the intro
      length = Math.min(file.duration, MAX_FILE_S);
      const src = ctx.createBufferSource();
      const g = ctx.createGain();
      src.buffer = file;
      const t0 = ctx.currentTime;
      g.gain.setValueAtTime(0.9, t0);
      g.gain.setValueAtTime(0.9, t0 + Math.max(0, length - 0.4));
      g.gain.linearRampToValueAtTime(0.0001, t0 + length);
      src.connect(g).connect(ctx.destination);
      src.start(t0);
      src.stop(t0 + length + 0.05);
    } else {
      compose(ctx);
    }
    markPlayed();
    setTimeout(
      () => void ctx.close().catch(() => undefined),
      (length + 0.6) * 1000,
    );
  };

  return {
    needsGesture: ctx.state !== "running",
    play: () => {
      if (done) return;
      // resume() runs synchronously inside the click, which is what the
      // browser requires; the sound itself starts once the file is ready
      const resumed =
        ctx.state === "running" ? Promise.resolve() : ctx.resume();
      void Promise.all([resumed, loadedOrLate()]).then(start, () => undefined);
    },
    stop: () => {
      if (!done) void ctx.close().catch(() => undefined);
    },
  };
}
