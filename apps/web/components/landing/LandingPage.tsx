/* eslint-disable react/no-unescaped-entities */
/* eslint-disable @next/next/no-img-element */
import Link from 'next/link';
import { OrbitalGlobe } from './OrbitalGlobe';
import { StarField } from './StarField';
import { ScrollReveal, ScrollRevealGroup } from './ScrollReveal';
import { BootReadout } from './BootReadout';
import './landing.css';

export default function LandingPage() {
  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50 bg-surface-container-lowest/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
        <div className="h-16 w-full px-margin flex items-center justify-between gap-space-md">
          <div className="flex items-center gap-space-lg">
            <a
              className="flex items-center gap-space-sm"
              data-path="overview"
              href="#"
            >
              <img
                alt="SATQUERY AI military aerospace intelligence emblem, orbital trajectory rings around a stylized synthetic aperture radar aperture icon, neon lime #c8f77a and electric cyan accents on dark hexagonal badge. Design context: - Primary color: #a3e635
- Font: manrope
- Mode: dark
- Roundness: rounded-sm
. The logo should be visually consistent with these brand tokens."
                className="h-8 w-auto object-contain"
                src="https://lh3.googleusercontent.com/aida/AEtjO1UbKmWi25aeyKbNarNgZW2R3tAMoyaKNkt16Eq2oxpUsQbidl6NupPiN2vOP95-8Jfc9G-qonnGEDpO902Z2dqHTqIOQJCCaU9JCWar0BGPNBzRkgy6N4qth7p62I4Mn8AfHzQh0t1DHGvC95pLWuJaI7O5lG8nihDp_Famfpi-t9tqJcnj6Du_pFfBP0g4rnsIwsYbynIK-FzHy9syxF5SJBA1PHVvAJXvgixY7eATtxh7XMEX5AFgn8A"
              />
              <span className="font-headline-md text-headline-md tracking-tight text-on-surface uppercase">
                SATQUERY<span className="text-primary">.AI</span>
              </span>
            </a>
            <div className="hidden xl:flex items-center gap-space-xs bg-surface-container-high px-space-sm py-space-xs rounded-full">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">
                SYS_STATUS // NOMINAL
              </span>
            </div>
          </div>
          <nav
            className="hidden lg:flex items-center gap-space-sm"
            data-active-classes="bg-surface-container-high text-on-surface rounded font-label-md text-label-md"
          >
            <a
              className="font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors px-space-sm py-space-xs"
              data-path="technology"
              href="#"
            >
              Technology
            </a>
            <a
              className="font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors px-space-sm py-space-xs"
              data-path="constellations"
              href="#"
            >
              Constellations
            </a>
            <a
              className="font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors px-space-sm py-space-xs"
              data-path="synthetic-intelligence"
              href="#"
            >
              Synthetic Intelligence
            </a>
            <a
              className="font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors px-space-sm py-space-xs"
              data-path="documentation"
              href="#"
            >
              Documentation
            </a>
            <a
              className="font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors px-space-sm py-space-xs"
              data-path="enterprise-and-defense"
              href="#"
            >
              Enterprise &amp; Defense
            </a>
          </nav>
          <div className="flex items-center gap-space-md">
            <a
              className="hidden sm:inline-flex font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors px-space-sm py-space-xs"
              data-path="request-access"
              href="#"
            >
              Request Access
            </a>
            <Link
              className="inline-flex items-center gap-space-xs bg-primary-container text-on-primary font-label-md text-label-md px-space-md py-space-sm rounded-lg hover:bg-primary transition-all shadow-[0_0_12px_rgba(163,230,53,0.3)]"
              data-path="mission-console"
              href="/dashboard"
            >
              <span>Launch Mission Console</span>
              <span>→</span>
            </Link>
            <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
              <span className="material-symbols-outlined text-on-primary text-[18px]">
                person
              </span>
            </div>
          </div>
        </div>
      </header>
      <main className="w-full pt-16 bg-surface">
        <div className="flex flex-col w-full">
          {/* ── HERO ──────────────────────────────────────────── */}
          <section className="relative w-full overflow-hidden bg-surface-container-lowest -mt-16 pt-24 pb-16 lg:pb-24" style={{ minHeight: '100svh' }}>
            {/* Layer 0: stars (full-bleed, behind everything) */}
            <div className="absolute inset-0 z-0 pointer-events-none">
              <StarField />
            </div>

            {/* Layer 1: nebula/radial colour wash */}
            <div
              aria-hidden="true"
              className="absolute inset-0 z-0 pointer-events-none"
              style={{
                background:
                  'radial-gradient(ellipse 80% 60% at 65% 50%, rgba(163,230,53,0.07) 0%, rgba(74,158,255,0.05) 40%, transparent 70%),' +
                  'radial-gradient(ellipse 60% 80% at 30% 60%, rgba(0,219,233,0.05) 0%, transparent 60%)',
              }}
            />

            {/* Layer 2: the Earth — large, right-of-centre */}
            <div
              aria-hidden="true"
              className="absolute pointer-events-none"
              style={{
                right: '-5%',
                top: '50%',
                transform: 'translateY(-50%)',
                width: 'min(70vw, 700px)',
                height: 'min(70vw, 700px)',
                opacity: 0.92,
              }}
            >
              <OrbitalGlobe />
            </div>

            {/* Layer 3: gradient vignette to blend earth into page */}
            <div
              aria-hidden="true"
              className="absolute inset-0 z-0 pointer-events-none"
              style={{
                background:
                  'linear-gradient(to right, #0c0e13 30%, transparent 65%, transparent 80%, #0c0e13 100%),' +
                  'linear-gradient(to bottom, #0c0e13 0%, transparent 12%, transparent 88%, #0c0e13 100%)',
              }}
            />

            {/* Layer 4: HUD grid */}
            <div className="absolute inset-0 z-0 pointer-events-none opacity-20 bg-[linear-gradient(to_right,#8c947c12_1px,transparent_1px),linear-gradient(to_bottom,#8c947c12_1px,transparent_1px)] bg-[size:4rem_4rem]"></div>
            <div className="relative z-10 w-full px-margin flex flex-col items-start max-w-7xl mx-auto" style={{ minHeight: 'calc(100svh - 4rem)', justifyContent: 'center', paddingTop: '3rem', paddingBottom: '3rem' }}>
              <ScrollReveal delay={0}>
                <div className="inline-flex items-center gap-space-sm bg-surface-container/80 backdrop-blur-md px-space-md py-space-xs rounded-full shadow-lg mb-space-lg">
                  <span className="w-2.5 h-2.5 rounded-full bg-primary-container animate-pulse shadow-[0_0_8px_rgba(163,230,53,0.8)]"></span>
                  <span className="font-label-md text-label-md text-primary tracking-widest uppercase">
                    ORBITAL INTELLIGENCE // GEN-4 CONSTELLATION RECONNAISSANCE
                  </span>
                  <span className="text-outline-variant font-label-md">|</span>
                  <span className="font-label-sm text-label-sm text-secondary-fixed tracking-wider">
                    SWATH LATENCY: 0.84s
                  </span>
                </div>
              </ScrollReveal>

              <ScrollReveal delay={0.1}>
                <div className="mb-space-md max-w-2xl">
                  <h1 className="font-headline-xl text-headline-xl lg:text-[64px] lg:leading-[1.1] text-on-surface tracking-tight">
                    Ask a question.
                    <br />
                    <span className="text-primary selection:bg-primary selection:text-on-primary">
                      Get an answer with its evidence.
                    </span>
                  </h1>
                  <p className="mt-space-md font-body-lg text-body-lg text-on-surface-variant max-w-xl leading-relaxed">
                    Autonomous synthetic aperture radar (SAR) and multispectral
                    planetary inference. Penetrate 100% cloud cover, night-time
                    blindspots, and dense atmospheric canopy with autonomous
                    real-time geospatial agents.
                  </p>
                </div>
              </ScrollReveal>

              <ScrollReveal delay={0.2}>
              <div className="w-full max-w-4xl mt-space-md bg-surface-container-low/90 backdrop-blur-2xl rounded-xl shadow-2xl p-space-md sm:p-space-lg">
                <div className="flex items-center justify-between pb-space-sm mb-space-sm">
                  <div className="flex items-center gap-space-xs">
                    <span className="w-3 h-3 rounded-full bg-error/70"></span>
                    <span className="w-3 h-3 rounded-full bg-tertiary-container/70"></span>
                    <span className="w-3 h-3 rounded-full bg-primary-container/70"></span>
                    <span className="ml-space-sm font-label-sm text-label-sm text-on-surface-variant uppercase">
                      SATQUERY TELEMETRY DAEMON // TTY0_ORBITAL
                    </span>
                  </div>
                  <div className="flex items-center gap-space-sm font-label-sm text-label-sm text-outline">
                    <span>MODEL: hand-only-v2</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-primary-container"></span>
                    <span className="text-primary">ONLINE</span>
                  </div>
                </div>

                <div className="bg-surface-container-lowest/90 rounded-lg p-space-md font-label-md text-label-md flex flex-col gap-space-sm">
                  <div className="flex items-start gap-space-sm text-on-surface">
                    <span className="text-primary font-bold select-none">
                      &gt;&gt;
                    </span>
                    <div className="flex-1 font-label-md">
                      <span className="text-secondary">
                        $ satquery --target{" "}
                      </span>
                      <span className="text-tertiary-fixed font-semibold">
                        "Detect covert vessel dark fleets in Strait of Malacca
                        [AIS Disabled]"
                      </span>
                      <span className="text-on-surface-variant">
                        {" "}
                        --sensor sar-cband --confidence 0.95
                      </span>
                      <span className="inline-block w-2.5 h-4 bg-primary align-middle ml-1 animate-pulse"></span>
                    </div>
                  </div>

                  <div className="mt-space-xs bg-surface-container-high/60 rounded p-space-sm flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm">
                    <div className="flex items-center gap-space-sm font-label-md text-label-md text-primary">
                      <span className="material-symbols-outlined text-[18px]">
                        verified
                      </span>
                      <span>
                        14 Dark Vessels Tracked // 98.2% Confidence // 0.8s
                        InSAR Latency
                      </span>
                    </div>
                    <div className="flex items-center gap-space-xs font-label-sm text-label-sm text-secondary-fixed-dim">
                      <span>BOUNDS: [1.3521° N, 103.8198° E]</span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-between gap-space-md mt-space-md pt-space-xs">
                  <div className="flex items-center gap-space-sm w-full sm:w-auto">
                    <Link
                      href="/dashboard"
                      className="w-full sm:w-auto inline-flex items-center justify-center gap-space-xs bg-primary-container text-on-primary font-label-lg text-label-lg px-space-lg py-space-sm rounded-lg hover:bg-primary transition-all shadow-[0_0_20px_rgba(163,230,53,0.35)]"
                    >
                      <span>Launch Mission Console</span>
                      <span className="material-symbols-outlined text-[18px]">
                        arrow_forward
                      </span>
                    </Link>
                    <a
                      className="w-full sm:w-auto inline-flex items-center justify-center gap-space-xs bg-surface-variant text-on-surface font-label-lg text-label-lg px-space-md py-space-sm rounded-lg hover:bg-surface-bright transition-colors"
                      href="#pipeline"
                    >
                      <span className="material-symbols-outlined text-[18px]">
                        radar
                      </span>
                      <span>Sensor Fusion Demo</span>
                    </a>
                  </div>
                  <div className="hidden md:flex items-center gap-space-md font-label-sm text-label-sm text-outline">
                    <span className="flex items-center gap-1">
                      <span className="material-symbols-outlined text-[14px] text-primary">
                        lock
                      </span>{" "}
                      AES-256 GCM
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="material-symbols-outlined text-[14px] text-secondary">
                        satellite_alt
                      </span>{" "}
                      450+ NODES INDEXED
                    </span>
                  </div>
                </div>
              </div>
              </ScrollReveal>

              <ScrollRevealGroup className="w-full max-w-5xl grid grid-cols-2 md:grid-cols-4 gap-space-md mt-space-xl">
                <div className="bg-surface-container/60 backdrop-blur-md p-space-md rounded-xl flex flex-col gap-1 shadow-md">
                  <div className="flex items-center justify-between text-outline">
                    <span className="font-label-sm text-label-sm uppercase">
                      Held-out IoU Benchmark
                    </span>
                    <span className="material-symbols-outlined text-[16px] text-primary">
                      troubleshoot
                    </span>
                  </div>
                  <span className="font-label-lg text-[28px] font-bold text-primary">
                    0.435
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    vs 0.204 Classical Baseline
                  </span>
                  <p className="font-mono text-[10px] leading-snug text-on-surface-variant mt-1">
                    Intersection-over-union on whole held-out regions. Accuracy is not
                    quoted: water is 11% of pixels, so predicting none scores 89%.
                  </p>
                </div>
                <div className="bg-surface-container/60 backdrop-blur-md p-space-md rounded-xl flex flex-col gap-1 shadow-md">
                  <div className="flex items-center justify-between text-outline">
                    <span className="font-label-sm text-label-sm uppercase">
                      Inference Cadence
                    </span>
                    <span className="material-symbols-outlined text-[16px] text-secondary">
                      bolt
                    </span>
                  </div>
                  <span className="font-label-lg text-[28px] font-bold text-secondary">
                    &lt; 1.8s
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    Global constellation query
                  </span>
                </div>
                <div className="bg-surface-container/60 backdrop-blur-md p-space-md rounded-xl flex flex-col gap-1 shadow-md">
                  <div className="flex items-center justify-between text-outline">
                    <span className="font-label-sm text-label-sm uppercase">
                      SAR Penetration
                    </span>
                    <span className="material-symbols-outlined text-[16px] text-primary">
                      cloud_done
                    </span>
                  </div>
                  <span className="font-label-lg text-[28px] font-bold text-on-surface">
                    100%
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    All-weather C/X-band active
                  </span>
                </div>
                <div className="bg-surface-container/60 backdrop-blur-md p-space-md rounded-xl flex flex-col gap-1 shadow-md">
                  <div className="flex items-center justify-between text-outline">
                    <span className="font-label-sm text-label-sm uppercase">
                      Integrated Nodes
                    </span>
                    <span className="material-symbols-outlined text-[16px] text-tertiary-fixed">
                      satellite
                    </span>
                  </div>
                  <span className="font-label-lg text-[28px] font-bold text-tertiary-fixed">
                    450+
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    ICEYE, Sentinel, Landsat, Capella
                  </span>
                </div>
              </ScrollRevealGroup>

              {/* The console's real startup checks, in the reference film's numbered
                  readout. Deliberately retained from the previous landing: a check
                  that has not reached 100 reads Partial, never green (P5-15). */}
              <div className="w-full max-w-5xl mx-auto mt-space-xl">
                <BootReadout />
              </div>
            </div>
          </section>

          <section
            className="w-full bg-surface-container-low py-space-xl relative"
            id="pipeline"
          >
            <div className="w-full max-w-7xl mx-auto px-margin">
              <div className="flex flex-col md:flex-row md:items-end justify-between mb-space-xl gap-space-md">
                <div>
                  <div className="inline-flex items-center gap-space-xs font-label-md text-label-md text-primary uppercase tracking-widest mb-space-xs">
                    <span className="material-symbols-outlined text-[16px]">
                      account_tree
                    </span>
                    Multi-Agent Ground Truth Engine
                  </div>
                  <h2 className="font-headline-lg text-headline-lg text-on-surface">
                    From Question to Coherent Radar Phase Audit
                  </h2>
                </div>
                <p className="font-body-md text-body-md text-on-surface-variant max-w-md">
                  SATQUERY decomposes natural language queries into automated
                  ephemeris passes, raw InSAR coherence calculations, and
                  verifiable polygon bounding boxes.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-center">
                <div className="lg:col-span-6 flex flex-col gap-space-md">
                  <div className="bg-surface-container/90 backdrop-blur-md p-space-md rounded-xl flex gap-space-md items-start shadow-md hover:bg-surface-container-high/90 transition-colors">
                    <span className="font-label-lg text-label-lg text-primary bg-primary/10 px-2 py-1 rounded">
                      01
                    </span>
                    <div className="flex flex-col">
                      <span className="font-headline-md text-headline-md text-on-surface">
                        Natural Language Geocoding
                      </span>
                      <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">
                        Translates ambiguous situational queries into exact
                        Military Grid Reference System (MGRS), hydrographic
                        bounding boxes, and ephemeris target coordinates.
                      </p>
                      <div className="mt-2 font-label-sm text-label-sm text-outline-variant flex items-center gap-space-xs">
                        <span>PARSER: SPATIAL-TRANSFORMER-XL</span>
                        <span>•</span>
                        <span className="text-primary">
                          LAT/LON RECONSTRUCTED
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-surface-container/90 backdrop-blur-md p-space-md rounded-xl flex gap-space-md items-start shadow-md hover:bg-surface-container-high/90 transition-colors">
                    <span className="font-label-lg text-label-lg text-secondary bg-secondary/10 px-2 py-1 rounded">
                      02
                    </span>
                    <div className="flex flex-col">
                      <span className="font-headline-md text-headline-md text-on-surface">
                        Orbital Swath Retasking &amp; Ephemeris Lookups
                      </span>
                      <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">
                        Dynamic telemetry arbitration across ascending and
                        descending orbit tracks. Selects optimal incidence
                        angles to eliminate shadow occlusions.
                      </p>
                      <div className="mt-2 font-label-sm text-label-sm text-outline-variant flex items-center gap-space-xs">
                        <span>PROPAGATION: SGP4 VECTOR</span>
                        <span>•</span>
                        <span className="text-secondary">
                          SWATH INTERSECT 11.2s
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-surface-container/90 backdrop-blur-md p-space-md rounded-xl flex gap-space-md items-start shadow-md hover:bg-surface-container-high/90 transition-colors">
                    <span className="font-label-lg text-label-lg text-tertiary-fixed bg-tertiary/10 px-2 py-1 rounded">
                      03
                    </span>
                    <div className="flex flex-col">
                      <span className="font-headline-md text-headline-md text-on-surface">
                        Synthetic Aperture Radar Phase Change Matrix
                      </span>
                      <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">
                        Computes differential interferometry (DInSAR) and
                        complex coherence. Identifies surface anomalies
                        undetectable to the human eye or standard optical
                        lenses.
                      </p>
                      <div className="mt-2 font-label-sm text-label-sm text-outline-variant flex items-center gap-space-xs">
                        <span>BAND: C-BAND 5.405 GHZ</span>
                        <span>•</span>
                        <span className="text-tertiary-fixed">
                          PHASE RESIDUAL NOMINAL
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-surface-container/90 backdrop-blur-md p-space-md rounded-xl flex gap-space-md items-start shadow-md hover:bg-surface-container-high/90 transition-colors">
                    <span className="font-label-lg text-label-lg text-primary-container bg-primary-container/20 text-primary px-2 py-1 rounded">
                      04
                    </span>
                    <div className="flex flex-col">
                      <span className="font-headline-md text-headline-md text-on-surface">
                        Evidence Synthesis &amp; Geotagged Audit Trail
                      </span>
                      <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">
                        Generates cryptographic GeoJSON polygons with direct raw
                        telemetry links, eliminating synthetic hallucination in
                        defense and compliance ops.
                      </p>
                      <div className="mt-2 font-label-sm text-label-sm text-outline-variant flex items-center gap-space-xs">
                        <span>PROVENANCE: SHA-256 HASH</span>
                        <span>•</span>
                        <span className="text-primary">EVIDENCE CERTIFIED</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-6 bg-surface-container-lowest rounded-2xl overflow-hidden shadow-2xl relative">
                  <div className="relative w-full aspect-square sm:aspect-[4/3] overflow-hidden">
                    <img
                      alt="Thermal IR Sat Recon Amazon Basin Tactical Target"
                      className="w-full h-full object-cover"
                      src="https://lh3.googleusercontent.com/aida/AEtjO1Wx99JYPT51oXzArf23Lp4kP0PABsiadF0zYWzqambM4MO7nbH9VDV2Twh_DA_3ajzZccProNYFwcXM_DXer6F97WntPswrd-RPhbXJN8RfAtu2jhuy18wvsUJNkeyz2nMCmywxX-twIOd8csgHT4FiLcT3_zhkl_Lbl5s_sWKfk5cgOlD4JJSYPL7DmzI6AhkjGZ7O_wcvOmGgubo2ieQis_mHOS1cYZrz-Rv6mrhd58nmVAMKeKjTFKLc"
                    />

                    <div className="absolute inset-0 p-space-md flex flex-col justify-between pointer-events-none">
                      <div className="flex items-center justify-between bg-surface-container-lowest/80 backdrop-blur-md px-space-sm py-space-xs rounded font-label-sm text-label-sm text-secondary-fixed">
                        <span className="flex items-center gap-1 font-semibold text-primary">
                          <span className="w-2 h-2 rounded-full bg-primary animate-ping"></span>{" "}
                          LIVE RECON // AOI-AMZ-04B
                        </span>
                        <span className="text-on-surface-variant">
                          SENSORS: SAR C-BAND + THERMAL IR
                        </span>
                      </div>

                      <div className="self-center my-auto relative w-48 h-48 sm:w-60 sm:h-60 rounded bg-primary/5 flex items-center justify-center">
                        <div className="absolute top-0 left-0 w-4 h-4 bg-primary rounded-none"></div>
                        <div className="absolute top-0 right-0 w-4 h-4 bg-primary rounded-none"></div>
                        <div className="absolute bottom-0 left-0 w-4 h-4 bg-primary rounded-none"></div>
                        <div className="absolute bottom-0 right-0 w-4 h-4 bg-primary rounded-none"></div>
                        <div className="text-center font-label-sm text-label-sm bg-surface-container-lowest/90 px-space-xs py-0.5 rounded text-primary">
                          TARGET LOCK: 98.7% CONFIDENCE
                        </div>
                      </div>

                      <div className="flex items-center justify-between bg-surface-container-lowest/85 backdrop-blur-md p-space-xs rounded font-label-sm text-label-sm text-on-surface-variant">
                        <span className="text-secondary font-mono">
                          LAT: -3.4653° | LON: -62.2159°
                        </span>
                        <span className="text-primary font-mono">
                          CANOPY DEFICIT: -1,420 M²
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="p-space-md bg-surface-container flex flex-col sm:flex-row items-center justify-between gap-space-sm font-label-sm text-label-sm">
                    <div className="flex items-center gap-space-sm">
                      <span className="text-on-surface font-semibold">
                        Sensor Mode Arbitration:
                      </span>
                      <span className="px-space-xs py-0.5 bg-surface-container-high rounded text-primary font-mono">
                        VV / VH Polarization
                      </span>
                    </div>
                    <div className="flex items-center gap-space-sm text-outline">
                      <span>ORBIT TRACK #142</span>
                      <span>•</span>
                      <span className="text-secondary">ELEVATION 541.4 KM</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="w-full bg-surface py-space-xl relative">
            <div className="w-full max-w-7xl mx-auto px-margin">
              <div className="text-center max-w-3xl mx-auto mb-space-xl">
                <span className="font-label-md text-label-md text-secondary uppercase tracking-widest">
                  Global Ephemeris Fleet
                </span>
                <h2 className="font-headline-lg text-headline-lg text-on-surface mt-space-xs">
                  Multi-Constellation Sensor Arbitration
                </h2>
                <p className="font-body-md text-body-md text-on-surface-variant mt-space-xs">
                  SatQuery unifies commercially and sovereignly operated orbital
                  platforms into a synchronized, query-ready planetary index.
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-space-md">
                <div className="bg-surface-container p-space-lg rounded-xl flex flex-col justify-between shadow-lg hover:bg-surface-container-high transition-all">
                  <div>
                    <div className="flex items-center justify-between mb-space-md">
                      <span className="font-label-sm text-label-sm text-primary uppercase bg-primary/10 px-2 py-0.5 rounded">
                        SAR // C-BAND
                      </span>
                      <span className="material-symbols-outlined text-outline text-[20px]">
                        radar
                      </span>
                    </div>
                    <h3 className="font-headline-md text-headline-md text-on-surface">
                      Sentinel-1 (ESA)
                    </h3>
                    <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-xs">
                      Global interferometry repeat pass every 6–12 days. High
                      surface moisture and ground displacement sensitivity.
                    </p>
                  </div>
                  <div className="mt-space-lg pt-space-sm bg-surface-container-low/50 p-space-xs rounded font-label-sm text-label-sm flex justify-between text-outline">
                    <span>RES: 5M × 20M</span>
                    <span className="text-primary">100% UNRESTRICTED</span>
                  </div>
                </div>

                <div className="bg-surface-container p-space-lg rounded-xl flex flex-col justify-between shadow-lg hover:bg-surface-container-high transition-all">
                  <div>
                    <div className="flex items-center justify-between mb-space-md">
                      <span className="font-label-sm text-label-sm text-secondary uppercase bg-secondary/10 px-2 py-0.5 rounded">
                        SAR // X-BAND
                      </span>
                      <span className="material-symbols-outlined text-secondary text-[20px]">
                        satellite_alt
                      </span>
                    </div>
                    <h3 className="font-headline-md text-headline-md text-on-surface">
                      ICEYE &amp; Capella
                    </h3>
                    <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-xs">
                      Sub-meter spotlight resolution. Rapid retasking in under
                      60 minutes for high-value maritime and tactical targets.
                    </p>
                  </div>
                  <div className="mt-space-lg pt-space-sm bg-surface-container-low/50 p-space-xs rounded font-label-sm text-label-sm flex justify-between text-outline">
                    <span>RES: 0.5M SPOTLIGHT</span>
                    <span className="text-secondary">DYNAMIC TASKING</span>
                  </div>
                </div>

                <div className="bg-surface-container p-space-lg rounded-xl flex flex-col justify-between shadow-lg hover:bg-surface-container-high transition-all">
                  <div>
                    <div className="flex items-center justify-between mb-space-md">
                      <span className="font-label-sm text-label-sm text-tertiary-fixed uppercase bg-tertiary/10 px-2 py-0.5 rounded">
                        OPTICAL + SWIR
                      </span>
                      <span className="material-symbols-outlined text-tertiary-fixed text-[20px]">
                        visibility
                      </span>
                    </div>
                    <h3 className="font-headline-md text-headline-md text-on-surface">
                      Landsat-9 &amp; S-2
                    </h3>
                    <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-xs">
                      13-band multispectral reflectance. Thermal infrared bands
                      calibrated for wildfire boundary and heat-signature
                      auditing.
                    </p>
                  </div>
                  <div className="mt-space-lg pt-space-sm bg-surface-container-low/50 p-space-xs rounded font-label-sm text-label-sm flex justify-between text-outline">
                    <span>RES: 10M–30M BANDS</span>
                    <span className="text-tertiary-fixed">
                      SPECTRAL SIGNATURE
                    </span>
                  </div>
                </div>

                <div className="bg-surface-container p-space-lg rounded-xl flex flex-col justify-between shadow-lg hover:bg-surface-container-high transition-all">
                  <div>
                    <div className="flex items-center justify-between mb-space-md">
                      <span className="font-label-sm text-label-sm text-primary uppercase bg-primary/10 px-2 py-0.5 rounded">
                        DAILY CADENCE
                      </span>
                      <span className="material-symbols-outlined text-primary text-[20px]">
                        public
                      </span>
                    </div>
                    <h3 className="font-headline-md text-headline-md text-on-surface">
                      PlanetScope Flocks
                    </h3>
                    <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-xs">
                      200+ micro-satellites providing complete planet-wide
                      3-meter optical sweeps every 24 hours.
                    </p>
                  </div>
                  <div className="mt-space-lg pt-space-sm bg-surface-container-low/50 p-space-xs rounded font-label-sm text-label-sm flex justify-between text-outline">
                    <span>RES: 3.0M CONTINUOUS</span>
                    <span className="text-primary">DAILY ORTHOMOSAIC</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="w-full bg-surface-container-lowest py-space-xl relative">
            <div className="w-full max-w-7xl mx-auto px-margin">
              <div className="flex flex-col md:flex-row md:items-end justify-between mb-space-xl gap-space-md">
                <div>
                  <span className="font-label-md text-label-md text-primary uppercase tracking-widest">
                    Tactical Applications
                  </span>
                  <h2 className="font-headline-lg text-headline-lg text-on-surface mt-space-xs">
                    Engineered for Sovereign Defense &amp; Critical
                    Infrastructure
                  </h2>
                </div>
                <p className="font-body-md text-body-md text-on-surface-variant max-w-md">
                  Providing operational decision advantages when adversary
                  camouflage, cloud cover, or darkness denies conventional
                  optical reconnaissance.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-space-lg">
                <div className="bg-surface-container-low rounded-xl p-space-lg flex flex-col justify-between shadow-xl hover:bg-surface-container transition-all">
                  <div>
                    <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center text-secondary mb-space-md">
                      <span className="material-symbols-outlined text-[28px]">
                        directions_boat
                      </span>
                    </div>
                    <span className="font-label-sm text-label-sm text-secondary uppercase tracking-wider">
                      MARITIME DOMAIN AWARENESS
                    </span>
                    <h3 className="font-headline-md text-headline-md text-on-surface mt-1">
                      Dark Vessel Interception
                    </h3>
                    <p className="font-body-md text-body-md text-on-surface-variant mt-space-sm">
                      Detect vessels with deactivated AIS transponders using
                      Coherent Radar Backscatter. Calculate speed, heading, and
                      displacement wake in open waters or contested EEZ zones.
                    </p>
                  </div>
                  <div className="mt-space-lg pt-space-sm bg-surface-container-lowest/80 rounded p-space-sm font-label-sm text-label-sm text-on-surface flex flex-col gap-1">
                    <div className="flex justify-between text-outline">
                      <span>TARGET TYPE:</span>{" "}
                      <span className="text-on-surface">SHADOW TANKERS</span>
                    </div>
                    <div className="flex justify-between text-outline">
                      <span>DETECTION RECALL:</span>{" "}
                      <span className="text-primary font-bold">99.4%</span>
                    </div>
                  </div>
                </div>

                <div className="bg-surface-container-low rounded-xl p-space-lg flex flex-col justify-between shadow-xl hover:bg-surface-container transition-all">
                  <div>
                    <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center text-primary mb-space-md">
                      <span className="material-symbols-outlined text-[28px]">
                        forest
                      </span>
                    </div>
                    <span className="font-label-sm text-label-sm text-primary uppercase tracking-wider">
                      ENVIRONMENTAL SOVEREIGNTY
                    </span>
                    <h3 className="font-headline-md text-headline-md text-on-surface mt-1">
                      Canopy Loss Verification
                    </h3>
                    <p className="font-body-md text-body-md text-on-surface-variant mt-space-sm">
                      Continuous radar phase interferometry cuts straight
                      through permanent tropical rainclouds in the Amazon and
                      Congo basins, detecting illegal clearings and haul roads
                      in under 24 hours.
                    </p>
                  </div>
                  <div className="mt-space-lg pt-space-sm bg-surface-container-lowest/80 rounded p-space-sm font-label-sm text-label-sm text-on-surface flex flex-col gap-1">
                    <div className="flex justify-between text-outline">
                      <span>CLOUD PENETRATION:</span>{" "}
                      <span className="text-on-surface">100% CONSTANT</span>
                    </div>
                    <div className="flex justify-between text-outline">
                      <span>SUB-ACRE ALERT:</span>{" "}
                      <span className="text-primary font-bold">
                        &lt; 6 HOURS
                      </span>
                    </div>
                  </div>
                </div>

                <div className="bg-surface-container-low rounded-xl p-space-lg flex flex-col justify-between shadow-xl hover:bg-surface-container transition-all">
                  <div>
                    <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center text-tertiary-fixed mb-space-md">
                      <span className="material-symbols-outlined text-[28px]">
                        shield
                      </span>
                    </div>
                    <span className="font-label-sm text-label-sm text-tertiary-fixed uppercase tracking-wider">
                      DEFENSE RECONNAISSANCE
                    </span>
                    <h3 className="font-headline-md text-headline-md text-on-surface mt-1">
                      Airbase &amp; Port Displacement
                    </h3>
                    <p className="font-body-md text-body-md text-on-surface-variant mt-space-sm">
                      Millimeter-grade surface deformation audits on remote
                      airstrips, missile silos, and ammunition depots. Track
                      changes in aircraft parking patterns without waiting for
                      clear daylight.
                    </p>
                  </div>
                  <div className="mt-space-lg pt-space-sm bg-surface-container-lowest/80 rounded p-space-sm font-label-sm text-label-sm text-on-surface flex flex-col gap-1">
                    <div className="flex justify-between text-outline">
                      <span>SUBSIDENCE SENSITIVITY:</span>{" "}
                      <span className="text-on-surface">± 1.2 MM</span>
                    </div>
                    <div className="flex justify-between text-outline">
                      <span>CLASSIFIED AIR-GAP:</span>{" "}
                      <span className="text-tertiary-fixed font-bold">
                        READY
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="w-full bg-surface-container py-space-xl relative">
            <div className="w-full max-w-7xl mx-auto px-margin">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg">
                <div className="lg:col-span-7 flex flex-col gap-space-lg">
                  <div>
                    <span className="font-label-md text-label-md text-primary uppercase tracking-widest">
                      Empirical Zero-Shot Validation
                    </span>
                    <h2 className="font-headline-lg text-headline-lg text-on-surface mt-space-xs">
                      Proven Generalization on Held-Out Topographies
                    </h2>
                    <p className="font-body-md text-body-md text-on-surface-variant mt-space-xs">
                      Unlike traditional thresholding algorithms that require
                      manual manual parameter recalibration across regions,
                      SatQuery delivers over 2.1× higher precision on
                      never-before-seen terrain.
                    </p>
                  </div>

                  <div className="bg-surface-container-low rounded-xl p-space-lg flex flex-col sm:flex-row items-center justify-between gap-space-md shadow-lg">
                    <div className="flex flex-col">
                      <span className="font-label-sm text-label-sm text-outline uppercase">
                        Held-out IoU Score
                      </span>
                      <span className="font-label-lg text-[36px] font-bold text-primary">
                        0.435
                      </span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">
                        India + Somalia flood regions (never trained on)
                      </span>
                    </div>
                    <div className="h-12 w-px bg-surface-variant hidden sm:block"></div>
                    <div className="flex flex-col">
                      <span className="font-label-sm text-label-sm text-outline uppercase">
                        Classical Baseline
                      </span>
                      <span className="font-label-lg text-[36px] font-bold text-outline">
                        0.204
                      </span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">
                        Otsu log-ratio thresholding
                      </span>
                    </div>
                    <div className="h-12 w-px bg-surface-variant hidden sm:block"></div>
                    <div className="flex flex-col">
                      <span className="font-label-sm text-label-sm text-outline uppercase">
                        Hand-labelled Chips
                      </span>
                      <span className="font-label-lg text-[36px] font-bold text-secondary">
                        400
                      </span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">
                        Sen1Floods11 benchmark dataset
                      </span>
                    </div>
                  </div>

                  <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-2xl font-label-md text-label-md">
                    <div className="flex items-center justify-between pb-space-xs mb-space-xs text-outline">
                      <span className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-[16px] text-primary">
                          terminal
                        </span>{" "}
                        python-sdk / satquery.py
                      </span>
                      <span className="text-on-surface-variant">
                        pip install satquery
                      </span>
                    </div>
                    <pre className="overflow-x-auto text-on-surface font-mono p-space-xs leading-relaxed">
                      <span className="text-on-surface-variant">
                        # Initialize aerospace mission client
                      </span>
                      <span className="text-secondary">import</span> satquery
                      client = satquery.
                      <span className="text-primary">Client</span>
                      (api_key=satquery.ORBITAL_SECRET)
                      <span className="text-on-surface-variant">
                        # Natural language orbital dispatch
                      </span>
                      mission = client.
                      <span className="text-primary">query</span>( prompt=
                      <span className="text-tertiary-fixed">
                        "Scan Spratly Reef for unannounced dredger flotillas"
                      </span>
                      , sensor=
                      <span className="text-secondary">"sar-cband"</span>,
                      min_confidence=<span className="text-primary">0.92</span>)
                      <span className="text-secondary">for</span> target{" "}
                      <span className="text-secondary">in</span>{" "}
                      mission.evidence.polygons:
                      <span className="text-primary">print</span>(f
                      <span className="text-tertiary">
                        "Target Locked: {"{target.mgrs_coordinate}"} [
                        {"{target.confidence}"}%]"
                      </span>
                      )
                    </pre>
                  </div>
                </div>

                <div className="lg:col-span-5 bg-surface-container-lowest rounded-xl p-space-lg flex flex-col justify-between shadow-2xl">
                  <div>
                    <div className="flex items-center justify-between pb-space-sm mb-space-md">
                      <div className="flex items-center gap-space-xs">
                        <span className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse"></span>
                        <span className="font-headline-md text-headline-md text-on-surface">
                          System Checks
                        </span>
                      </div>
                      <span className="font-label-sm text-label-sm text-primary uppercase bg-primary/10 px-2 py-0.5 rounded">
                        ALL ACTIVE
                      </span>
                    </div>

                    <div className="flex flex-col gap-space-md font-label-md text-label-md">
                      <div className="flex items-center justify-between">
                        <div className="flex items-baseline gap-space-sm">
                          <span className="text-outline font-mono">01</span>
                          <div>
                            <div className="text-on-surface font-semibold">
                              Contract schema
                            </div>
                            <div className="text-on-surface-variant text-[11px] font-sans">
                              Active schema validation
                            </div>
                          </div>
                        </div>
                        <span className="text-primary font-mono font-bold">
                          100%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-baseline gap-space-sm">
                          <span className="text-outline font-mono">02</span>
                          <div>
                            <div className="text-on-surface font-semibold">
                              Gateway route table
                            </div>
                            <div className="text-on-surface-variant text-[11px] font-sans">
                              Direct Ka-band downlink
                            </div>
                          </div>
                        </div>
                        <span className="text-primary font-mono font-bold">
                          100%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-baseline gap-space-sm">
                          <span className="text-outline font-mono">03</span>
                          <div>
                            <div className="text-on-surface font-semibold">
                              Coastline geometry
                            </div>
                            <div className="text-on-surface-variant text-[11px] font-sans">
                              Hydrographic mask synced
                            </div>
                          </div>
                        </div>
                        <span className="text-primary font-mono font-bold">
                          100%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-baseline gap-space-sm">
                          <span className="text-outline font-mono">04</span>
                          <div>
                            <div className="text-on-surface font-semibold">
                              Orbital propagation
                            </div>
                            <div className="text-on-surface-variant text-[11px] font-sans">
                              SGP4 vector tracking
                            </div>
                          </div>
                        </div>
                        <span className="text-primary font-mono font-bold">
                          100%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-baseline gap-space-sm">
                          <span className="text-outline font-mono">05</span>
                          <div>
                            <div className="text-on-surface font-semibold">
                              Observation index
                            </div>
                            <div className="text-on-surface-variant text-[11px] font-sans">
                              Global spatial tree online
                            </div>
                          </div>
                        </div>
                        <span className="text-primary font-mono font-bold">
                          100%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-baseline gap-space-sm">
                          <span className="text-outline font-mono">06</span>
                          <div>
                            <div className="text-on-surface font-semibold">
                              Model — hand-only-v2
                            </div>
                            <div className="text-on-surface-variant text-[11px] font-sans">
                              Zero-shot inference weight
                            </div>
                          </div>
                        </div>
                        <span className="text-primary font-mono font-bold">
                          100%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-baseline gap-space-sm">
                          <span className="text-outline font-mono">07</span>
                          <div>
                            <div className="text-on-surface font-semibold">
                              Confidence calibration
                            </div>
                            <div className="text-on-surface-variant text-[11px] font-sans">
                              Otsu boundary margin
                            </div>
                          </div>
                        </div>
                        <span className="text-tertiary-fixed font-mono font-bold">
                          58%
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-space-lg pt-space-md bg-surface-container rounded p-space-sm flex items-center justify-between font-label-sm text-label-sm text-outline">
                    <span>DAEMON ID: ORBITAL-044-B</span>
                    <span className="text-secondary">UTC 14:02:18</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="w-full bg-surface-container-lowest py-space-xl lg:py-28 relative overflow-hidden">
            <div className="absolute inset-0 bg-radial from-primary/10 via-transparent to-transparent pointer-events-none"></div>
            <div className="relative z-10 w-full max-w-5xl mx-auto px-margin text-center flex flex-col items-center">
              <span className="font-label-md text-label-md text-primary uppercase tracking-widest mb-space-xs">
                DIRECT FLIGHT OPERATIONS
              </span>
              <h2 className="font-headline-xl text-headline-xl lg:text-[56px] text-on-surface tracking-tight max-w-3xl">
                Direct Orbital Command at Your Fingertips.
              </h2>
              <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mt-space-md">
                Deploy natural language mission directives straight into space.
                Get unassailable military-grade geospatial evidence in seconds.
              </p>
              <div className="flex flex-col sm:flex-row items-center gap-space-md mt-space-xl">
                <a
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-space-xs bg-primary-container text-on-primary font-label-lg text-label-lg px-space-xl py-space-md rounded-lg hover:bg-primary transition-all shadow-[0_0_24px_rgba(163,230,53,0.4)]"
                  href="#"
                >
                  <span>Enter Mission Console</span>
                  <span className="material-symbols-outlined text-[20px]">
                    terminal
                  </span>
                </a>
                <a
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-space-xs bg-surface-container-high text-on-surface font-label-lg text-label-lg px-space-xl py-space-md rounded-lg hover:bg-surface-variant transition-colors"
                  href="#"
                >
                  <span className="material-symbols-outlined text-[20px]">
                    calendar_today
                  </span>
                  <span>Schedule Classified Briefing</span>
                </a>
              </div>
              <div className="mt-space-xl flex flex-wrap items-center justify-center gap-space-lg font-label-sm text-label-sm text-outline">
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-[16px] text-primary">
                    verified_user
                  </span>{" "}
                  FedRAMP High Ready
                </span>
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-[16px] text-secondary">
                    lock
                  </span>{" "}
                  Air-Gapped Deployments
                </span>
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-[16px] text-tertiary-fixed">
                    satellite_alt
                  </span>{" "}
                  ITAR &amp; EAR Compliant
                </span>
              </div>
            </div>
          </section>
        </div>
      </main>
      <footer className="w-full bg-surface-container-lowest text-on-surface-variant pt-space-xl pb-space-lg">
        <div className="w-full px-margin">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-space-lg pb-space-xl">
            <div className="lg:col-span-2 flex flex-col gap-space-md">
              <div className="flex items-center gap-space-sm">
                <img
                  alt="SATQUERY AI military aerospace intelligence emblem, orbital trajectory rings around a stylized synthetic aperture radar aperture icon, neon lime #c8f77a and electric cyan accents on dark hexagonal badge. Design context: - Primary color: #a3e635
- Font: manrope
- Mode: dark
- Roundness: rounded-sm
. The logo should be visually consistent with these brand tokens."
                  className="h-7 w-auto object-contain"
                  src="https://lh3.googleusercontent.com/aida/AEtjO1UbKmWi25aeyKbNarNgZW2R3tAMoyaKNkt16Eq2oxpUsQbidl6NupPiN2vOP95-8Jfc9G-qonnGEDpO902Z2dqHTqIOQJCCaU9JCWar0BGPNBzRkgy6N4qth7p62I4Mn8AfHzQh0t1DHGvC95pLWuJaI7O5lG8nihDp_Famfpi-t9tqJcnj6Du_pFfBP0g4rnsIwsYbynIK-FzHy9syxF5SJBA1PHVvAJXvgixY7eATtxh7XMEX5AFgn8A"
                />
                <span className="font-headline-md text-headline-md tracking-tight text-on-surface">
                  SATQUERY<span className="text-primary">.AI</span>
                </span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant max-w-md">
                Autonomous spatial intelligence, multi-pass Synthetic Aperture
                Radar fusion, and orbital vector telemetry querying engineered
                for mission-critical situational awareness.
              </p>
              <div className="flex flex-wrap items-center gap-space-sm pt-space-xs">
                <span className="bg-surface-container-high font-label-sm text-label-sm text-on-surface px-space-sm py-space-xs rounded">
                  ITAR COMPLIANT
                </span>
                <span className="bg-surface-container-high font-label-sm text-label-sm text-on-surface px-space-sm py-space-xs rounded">
                  FEDRAMP HIGH READY
                </span>
                <span className="bg-surface-container-high font-label-sm text-label-sm text-on-surface px-space-sm py-space-xs rounded">
                  ISO/IEC 27001
                </span>
              </div>
            </div>
            <div className="flex flex-col gap-space-sm">
              <span className="font-label-md text-label-md text-on-surface uppercase">
                Orbital Systems
              </span>
              <a
                className="font-body-sm text-body-sm hover:text-on-surface transition-colors"
                href="#"
              >
                SAR Constellation X-9
              </a>
              <a
                className="font-body-sm text-body-sm hover:text-on-surface transition-colors"
                href="#"
              >
                Sub-Meter Radar Orthomosaics
              </a>
              <a
                className="font-body-sm text-body-sm hover:text-on-surface transition-colors"
                href="#"
              >
                Synthetic Target Acquisition
              </a>
              <a
                className="font-body-sm text-body-sm hover:text-on-surface transition-colors"
                href="#"
              >
                Ephemeris Telemetry Feeds
              </a>
            </div>
            <div className="flex flex-col gap-space-sm">
              <span className="font-label-md text-label-md text-on-surface uppercase">
                Defense &amp; Intel
              </span>
              <a
                className="font-body-sm text-body-sm hover:text-on-surface transition-colors"
                href="#"
              >
                Tactical Operations Center
              </a>
              <a
                className="font-body-sm text-body-sm hover:text-on-surface transition-colors"
                href="#"
              >
                Autonomous MGRS Vectoring
              </a>
              <a
                className="font-body-sm text-body-sm hover:text-on-surface transition-colors"
                href="#"
              >
                Air-Gapped Node Deployments
              </a>
              <a
                className="font-body-sm text-body-sm hover:text-on-surface transition-colors"
                href="#"
              >
                Cryptographic Audit Ledger
              </a>
            </div>
            <div className="flex flex-col gap-space-sm">
              <span className="font-label-md text-label-md text-on-surface uppercase">
                Telemetry Anchor
              </span>
              <div className="font-label-sm text-label-sm bg-surface-container-high p-space-sm rounded flex flex-col gap-space-xs">
                <span className="text-primary">
                  LAT 38.8977° N // LON 77.0365° W
                </span>
                <span className="text-on-surface-variant">
                  ALT 540.2 KM // INC 97.4° SSO
                </span>
                <span className="text-secondary">
                  LINK: KA-BAND SECURE DOWNLINK
                </span>
                <span className="text-on-surface-variant">
                  LATENCY: 18.4 MS UTC
                </span>
              </div>
            </div>
          </div>
          <div className="pt-space-lg flex flex-col md:flex-row items-center justify-between gap-space-md font-label-sm text-label-sm text-on-surface-variant">
            <div className="flex items-center gap-space-md">
              <span>© 2025 SATQUERY AI TECHNOLOGIES INC.</span>
              <span>ORBITAL SECTOR 04</span>
            </div>
            <div className="flex items-center gap-space-lg">
              <a className="hover:text-on-surface transition-colors" href="#">
                Security Directive
              </a>
              <a className="hover:text-on-surface transition-colors" href="#">
                Telemetry API Status
              </a>
              <a className="hover:text-on-surface transition-colors" href="#">
                Privacy Framework
              </a>
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
