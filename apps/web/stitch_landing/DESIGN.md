---
name: Orbital Telemetry & Reconnaissance HUD
colors:
  surface: '#111319'
  surface-dim: '#111319'
  surface-bright: '#37393f'
  surface-container-lowest: '#0c0e13'
  surface-container-low: '#191c21'
  surface-container: '#1d2025'
  surface-container-high: '#282a30'
  surface-container-highest: '#33353b'
  on-surface: '#e2e2ea'
  on-surface-variant: '#c2cab0'
  inverse-surface: '#e2e2ea'
  inverse-on-surface: '#2e3036'
  outline: '#8c947c'
  outline-variant: '#424936'
  surface-tint: '#98da27'
  primary: '#ccff80'
  on-primary: '#213600'
  primary-container: '#a3e635'
  on-primary-container: '#416400'
  inverse-primary: '#446900'
  secondary: '#d3fbff'
  on-secondary: '#00363a'
  secondary-container: '#00eefc'
  on-secondary-container: '#00686f'
  tertiary: '#ffecd9'
  on-tertiary: '#472a00'
  tertiary-container: '#ffc989'
  on-tertiary-container: '#805000'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#b2f746'
  primary-fixed-dim: '#98da27'
  on-primary-fixed: '#121f00'
  on-primary-fixed-variant: '#334f00'
  secondary-fixed: '#7df4ff'
  secondary-fixed-dim: '#00dbe9'
  on-secondary-fixed: '#002022'
  on-secondary-fixed-variant: '#004f54'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#111319'
  on-background: '#e2e2ea'
  surface-variant: '#33353b'
typography:
  headline-xl:
    fontFamily: Manrope
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.03em
  headline-xl-mobile:
    fontFamily: Manrope
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Manrope
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Manrope
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.08em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.06em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 9px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system establishes an aerospace-grade, mission-critical satellite reconnaissance and spatial analytics interface. Built for orbital flight directors, defense analysts, and autonomous intelligence operators, the visual aesthetic prioritizes ultra-dense situational awareness, zero-latency legibility, and high-stakes precision under extreme conditions.

The visual direction merges **Technical Glassmorphism** with **Aerospace Brutalism**:
- **Atmosphere:** Deep void blacks, sub-orbital dark charcoals, and razor-sharp 1px wireframe enclosures reminiscent of heads-up displays (HUD) and vector radar scopes.
- **Lighting & Focus:** Translucent smoked-glass panels layered directly over 3D geospatial globes, synthetic aperture radar (SAR) scans, and orbital vectors. Micro-accents in radar lime and electric cyan pierce through the low-reflectance canvas to instantly direct operational attention.
- **Emotional Response:** Surgical, authoritative, hyper-focused, and unmistakably state-of-the-art. Every visual artifact serves telemetry verification, spatial orientation, or system telemetry auditability.

## Colors

The palette is engineered exclusively around an ultra-deep void dark mode to preserve operator dark adaptation, minimize light bleed, and ensure maximum signal-to-noise ratio:

- **Surface Tiers:**
  - Base Void Canvas: `#07090e` (pure sub-orbital black)
  - Surface Glass Lower: `rgba(11, 15, 23, 0.72)` with 20px backdrop blur
  - Surface Glass Raised / Inspect: `rgba(18, 24, 38, 0.85)` with 28px backdrop blur
  - Structural Wire Boundaries: `rgba(255, 255, 255, 0.08)` (tactical default), scaling to `rgba(163, 230, 53, 0.35)` on active acquisition.
- **Signal Accents:**
  - **Radar Lime (`#a3e635` / `#c8f77a`):** Primary tracking, active satellite locks, verified ground truth, passing test suites, nominal telemetry health.
  - **Telemetry Electric Cyan (`#00f0ff` / `#38bdf8`):** Sensor swaths, synthetic aperture radar passes, orbital node paths, live network routing.
  - **Warning Amber (`#f59e0b`):** Propellant warnings, orbital drift margins, sensor degradation, and non-blocking anomaly thresholds.
  - **Alert Crimson (`#ef4444`):** Orbital collision risks, lost telemetry link, unauthorized vector alterations, system check hard failures.

## Typography

Typography enforces a strict operational dual-stack:
1. **Command Sans (Manrope & Inter):** Used for primary briefings, mission briefs, card titles, executive queries, and context overviews. Provides human-readable, geometric clarity at scale without visual fatigue.
2. **Telemetry Monospace (JetBrains Mono):** Reserved for technical instrumentation: GPS/geodetic coordinates (lat/long/alt), epoch timestamps, Keplerian orbital element vectors, confidence scores, raw downlink logs, and pass rates. Always formatted with uppercase tracking where applicable to simulate military telemetry consoles.

## Layout & Spacing

The interface implements a **Three-Tier Command HUD Grid** engineered for dense multi-spectral displays:
- **Left Wing (280px - 340px fixed or collapsible):** Mission brief, natural language agent query prompts, target acquisition inputs, and constellation tree filters.
- **Center Canvas (Fluid):** Primary 3D orbital globe / SAR orthomosaic canvas with floating telemetry crosshairs, coordinate pins, and active swath ground overlays.
- **Right Wing (320px - 400px fixed):** Measured model performance, IoU scores, orbital propagation vectors, and real-time system check arrays.

### Responsive Behavior
- **Desktop (1440px+):** Full 3-panel command array with edge-docked utility ribbons.
- **Tablet / Mid-Screen (768px - 1439px):** Canvas remains full-bleed; side panels convert into frosted floating sliding sheets invoked via hotkey or edge tabs.
- **Mobile (< 768px):** Primary canvas collapses to top half with a contextual bottom-sheet drawer system toggling between brief queries and subsystem telemetry checklists.

## Elevation & Depth

Visual hierarchy does not use diffuse drop shadows; instead, it utilizes **Luminescent Tonal Stratification and High-Attenuation Glassmorphism**:

- **Ground Level 0 (Orbital Viewport):** Deep void backdrop (`#07090e`) carrying the webgl globe, vector orbit lines, and latitude/longitude graticules.
- **Floating Telemetry Modules (Level 1):** Dark charcoal slate panels with `rgba(11, 15, 23, 0.75)` fill, `backdrop-filter: blur(24px)`, and a razor-thin border of `1px solid rgba(255, 255, 255, 0.08)`.
- **Target Locks & Critical Intercepts (Level 2):** Elevated panels with `rgba(18, 24, 38, 0.92)` fill, fine borders glowing subtly with primary radar lime `rgba(163, 230, 53, 0.35)`, and an interior top-edge highlight (`inset 0 1px 0 rgba(255, 255, 255, 0.12)`).
- **HUD Reticles & Overlays:** Pure 0-fill vector shapes bordered with electric cyan (`#00f0ff`) paired with faint neon outer glows (`0 0 12px rgba(0, 240, 255, 0.25)`).

## Shapes

The interface embraces a low-radius, tactical geometry (`roundedness: 1`):
- Standard panels, cards, and modal sheets: `4px` (`0.25rem`) corner radius.
- System pills, live metric badges, and interactive tags: `4px` (`0.25rem`) with chamfered or squared aesthetics.
- Outer dialogs and command consoles: strictly under `8px` (`0.5rem`).
- Crosshairs, reticle markers, and tick lines: strictly `0px` sharp vector geometry to sustain a surgical avionics apparatus feel.

## Components

### Buttons & Mission Triggers
- **Primary Mission Button:** High-contrast solid radar lime (`#a3e635`) with void black typography (`#07090e`), bold monospaced or sans weight, 4px border radius, accompanied by rightward micro-arrows or terminal glyphs (`→` / `↵`). Hover triggers a sharp neon lime rim-glow.
- **Ghost / Wireframe Trigger:** Transparent backdrop, 1px border `rgba(255,255,255,0.14)`, text in white or electric cyan (`#00f0ff`). Hover shifts border to `#00f0ff` and applies `rgba(0, 240, 255, 0.08)` inner fill.

### Telemetry Cards & Metric Containers
- Built on translucent slate backing with 1px border `rgba(255, 255, 255, 0.08)`.
- Header bars feature tracking metrics, sensor model hashes (`Model — hand-only-v2`), and live status indicators (pulsing 6px neon green dot).
- Content typography uses `JetBrains Mono` for large statistical numbers with adjacent dimmed unit labels.

### Checklists & Status Verification Nodes
- Monospaced numbering (`01`, `02`, `...`, `11`) aligned to the far left in dimmed zinc (`#71717a`).
- Right-aligned percentage health metrics (`100%`, `58%`) colored according to status: radar lime for nominal, amber for degraded, crimson for failure.
- Sub-labels render in small muted sans-serif directly under component descriptors.

### Inputs & Terminal Query Bars
- Sleek dark fields with a fixed blinking neon lime square or vertical terminal cursor (`❚`).
- Placeholder styled as terminal prompt (`Ask a question. Get an answer with its evidence.` or `Enter coordinates (MGRS / LatLon)...`).
- Active focus illuminates the container with a subtle 1px cyan outline and zero-blur border tint.

### Data Chips & Telemetry Badges
- Compact rectangular tags with `label-sm` monospaced type.
- Background `rgba(255,255,255,0.04)` with fine 1px border. Status-coded left borders (2px solid `#a3e635` or `#00f0ff`).