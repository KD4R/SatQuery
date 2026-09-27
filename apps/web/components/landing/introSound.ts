/**
 * The two-second opening sound, played once per browser -- the first time
 * someone opens the site -- while the SatQuery mark is in the middle.
 *
 * Synthesised with the Web Audio API, so there is no audio file to ship or
 * license: a low pad swells in, a tone sweeps up like a signal locking on, and
 * two soft pings land (a radar echo) as the cube settles. About 2 seconds.
 *
 * Browsers only allow sound after the visitor has interacted with a page. On a
 * truly first visit that usually means the sound cannot start on its own. So:
 * try to start it immediately; if the browser holds it, start it on the first
 * click or key press during the intro instead. It is marked as played only once
 * it has actually been heard, so a visitor who never got to hear it gets another
 * chance on their next visit -- and nobody hears it twice.
 */

const KEY = "sq-intro-sound-played";

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

/**
 * Plays the sound if this browser has never heard it. Returns a cleanup that
 * removes the gesture fallback (call it when the intro ends).
 */
export function playIntroSoundOnce(): () => void {
  if (typeof window === "undefined" || alreadyPlayed()) return () => {};
  const AC =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!AC) return () => {};

  let ctx: AudioContext;
  try {
    ctx = new AC();
  } catch {
    return () => {};
  }

  let done = false;
  const start = () => {
    if (done || ctx.state !== "running") return;
    done = true;
    compose(ctx);
    markPlayed();
    setTimeout(() => void ctx.close().catch(() => undefined), 2600);
    removeGesture();
  };

  const onGesture = () => {
    void ctx.resume().then(start, () => undefined);
  };
  const removeGesture = () => {
    window.removeEventListener("pointerdown", onGesture, true);
    window.removeEventListener("keydown", onGesture, true);
  };

  if (ctx.state === "running") start();
  else {
    void ctx.resume().then(start, () => undefined);
    window.addEventListener("pointerdown", onGesture, true);
    window.addEventListener("keydown", onGesture, true);
  }

  return () => {
    removeGesture();
    if (!done) void ctx.close().catch(() => undefined);
  };
}
