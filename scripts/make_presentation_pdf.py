#!/usr/bin/env python3
"""
scripts/make_presentation_pdf.py — build the SatQuery AI presentation PDF.

Every number is sourced from reports/evaluation.md or this repository's code;
nothing is invented. Output: SatQuery_Presentation.pdf (16:9 slides).
"""

from fpdf import FPDF

W, H = 297, 167  # mm, 16:9

INK = (232, 234, 237)
DIM = (154, 160, 166)
FAINT = (95, 99, 104)
BG = (10, 12, 14)
CARD = (16, 20, 24)
RED = (255, 59, 48)
GREEN = (80, 200, 120)
AMBER = (255, 159, 10)
BLUE = (90, 160, 255)

SRC_EVAL = "reports/evaluation.md (generated, fingerprinted)"


class Deck(FPDF):
    def __init__(self):
        # NB: passing orientation with a tuple format swaps it — format alone wins.
        super().__init__(unit="mm", format=(W, H))
        self.set_auto_page_break(False)
        self.set_margins(0, 0, 0)
        self.add_font("mono", "", "/System/Library/Fonts/Menlo.ttc")
        self.add_font("mono", "B", "/System/Library/Fonts/Menlo.ttc")

    # ── slide scaffolding ────────────────────────────────────────────────
    def slide(self, kicker, title, accent=GREEN):
        self.add_page()
        self.set_fill_color(*BG)
        self.rect(0, 0, W, H, "F")
        # header rule + kicker
        self.set_draw_color(*accent)
        self.set_line_width(0.6)
        self.line(14, 16, 14, 30)
        self.set_xy(20, 16)
        self.set_font("mono", "", 8)
        self.set_text_color(*accent)
        self.cell(0, 4, kicker.upper())
        self.set_xy(20, 21)
        self.set_font("mono", "B", 21)
        self.set_text_color(*INK)
        self.cell(0, 9, title)
        # footer
        self.set_font("mono", "", 7)
        self.set_text_color(*FAINT)
        self.set_y(H - 10)
        self.cell(14, 5, "SatQuery AI — natural-language satellite intelligence")
        self.set_x(-30)
        self.cell(16, 5, f"{self.page_no():02d}")

    def text_block(self, x, y, w, lines, size=11, lh=6.2, color=INK, bold=False):
        self.set_xy(x, y)
        self.set_font("mono", "B" if bold else "", size)
        self.set_text_color(*color)
        for ln in lines:
            self.cell(w, lh, ln, new_x="LMARGIN", new_y="NEXT")

    def card(self, x, y, w, h, accent):
        self.set_fill_color(*CARD)
        self.set_draw_color(*accent)
        self.set_line_width(0.35)
        self.rect(x, y, w, h, "DF")

    def bullets(self, x, y, w, items, size=10.5, lh=6.4, color=INK, gap=1.6):
        self.set_font("mono", "", size)
        self.set_text_color(*color)
        yy = y
        for it in items:
            self.set_xy(x, yy)
            self.set_text_color(*GREEN)
            self.cell(4, lh, "▸")
            self.set_xy(x + 4.5, yy)
            self.set_text_color(*color)
            # manual wrap to honour the width
            import fpdf
            remaining = it
            first = True
            while remaining:
                avail = (w - 4.5) if first else (w - 4.5)
                chunk = self._fit(remaining, avail, size)
                self.set_xy(x + 4.5, yy)
                self.cell(w - 4.5, lh, chunk, new_x="LMARGIN", new_y="NEXT")
                remaining = remaining[len(chunk):].lstrip()
                first = False
                if remaining:
                    yy += lh
            yy += lh + gap - lh if False else lh + gap
        return yy

    def _fit(self, text, width_mm, size):
        """Greedily fit text into width_mm at the current mono font size."""
        self.set_font("mono", "", size)
        words = text.split(" ")
        line = ""
        for word in words:
            trial = (line + " " + word).strip()
            if self.get_string_width(trial) <= width_mm or not line:
                line = trial
            else:
                break
        return line


def chips(d, x, y, pairs, per_row=2, cw=63, ch=17, accent=RED):
    for i, (cap, val) in enumerate(pairs):
        cx = x + (i % per_row) * (cw + 4)
        cy = y + (i // per_row) * (ch + 4)
        d.card(cx, cy, cw, ch, accent)
        d.set_xy(cx + 4, cy + 2.5)
        d.set_font("mono", "", 7.5)
        d.set_text_color(*DIM)
        d.cell(cw - 8, 4, cap.upper())
        d.set_xy(cx + 4, cy + 7.5)
        d.set_font("mono", "B", 12.5)
        d.set_text_color(*INK if accent != RED else RED)
        d.cell(cw - 8, 6, val)


# ── build ────────────────────────────────────────────────────────────────────
d = Deck()

# 1 — title
d.add_page()
d.set_fill_color(*BG)
d.rect(0, 0, W, H, "F")
d.set_draw_color(*GREEN)
d.set_line_width(0.8)
d.line(14, 40, 14, 70)
d.set_xy(20, 42)
d.set_font("mono", "", 10)
d.set_text_color(*GREEN)
d.cell(0, 5, "EARTH OBSERVATION  ·  EVIDENCE-FIRST  ·  AGENT ORCHESTRATED")
d.set_xy(20, 52)
d.set_font("mono", "B", 34)
d.set_text_color(*INK)
d.cell(0, 14, "SatQuery AI")
d.set_xy(20, 72)
d.set_font("mono", "", 12.5)
d.set_text_color(*DIM)
for i, ln in enumerate([
    "Ask a question about the Earth in plain language.",
    "An LLM agent plans the mission, arbitrates sensors, acquires imagery,",
    "runs flood-extent inference, and answers with provenance — or says why it can't.",
]):
    d.set_y(72 + i * 7)
    d.set_x(20)
    d.cell(0, 6, ln)
d.set_font("mono", "", 8)
d.set_text_color(*FAINT)
d.set_y(H - 12)
d.set_x(20)
d.cell(0, 5, "KD4R/SatQuery — branch swarali — deck figures sourced from reports/evaluation.md")

# 2 — the problem / theory
d.slide("Theory", "Why this is hard — and what honesty costs", accent=RED)
d.bullets(20, 38, 128, [
    "Floods are measured in clouds: monsoon events blind optical satellites,",
    "so the measurement must fall back to C-band SAR, which penetrates cloud",
    "but confuses smooth water with radar shadow behind terrain.",
    "",
    "A natural-language query must become a machine plan: intent extraction,",
    "AOI validation, sensor arbitration, acquisition, preprocessing, inference,",
    "change detection, evidence assembly — each step auditable.",
    "",
    "Accuracy is a trap on imbalanced data: water is 10.8% of scorable pixels,",
    "so a model predicting 'never water' scores 89.2% accuracy and 0.000 IoU.",
    "This is why every figure in this deck is IoU/F1, never accuracy.",
], size=9.8)
d.card(160, 38, 118, 78, AMBER)
d.text_block(166, 43, 106, [
    "THE HONESTY RULE",
    "",
    "A value the backend did not",
    "supply renders NOT AVAILABLE",
    "with a reason — never a 0,",
    "never a guess, never a demo",
    "fixture in live mode.",
    "",
    "A stage that analysed 46% of",
    "the AOI is marked DEGRADED,",
    "not green.",
], size=8.6, lh=5.9, color=INK)

# 3 — architecture
d.slide("Architecture", "Nine services, one gateway, zero browser trust")
d.card(18, 36, 84, 96, BLUE)
d.text_block(23, 40, 76, [
    "P1  GATEWAY  :8000",
    "  auth (JWT/RBAC), proxy,",
    "  rate limits, audit, WS bridge",
    "",
    "P1  MISSION  :8001",
    "  missions, AOIs, job registry",
    "",
    "P2  AGENT  :8002",
    "  LangGraph: plan → arbitrate →",
    "  acquire → analyse → evidence",
    "",
    "P3  INFERENCE  :8003",
    "P4  EO-DATA / GEO",
], size=8.4, lh=5.5)
d.card(108, 36, 84, 96, GREEN)
d.text_block(113, 40, 76, [
    "WEB (live)  :3002",
    "  Next.js 15 console",
    "",
    "WEB (demo)  :3010",
    "  NEXT_PUBLIC_DEMO_MODE=1",
    "  deterministic fixtures",
    "",
    "POSTGRES  :5433    REDIS  :6379",
    "  jobs + run state + pub/sub",
    "",
    "PROMETHEUS/GRAFANA, OTel,",
    "TITILER, MINIO — observability",
    "and raster tiles",
], size=8.4, lh=5.5)
d.card(198, 36, 82, 96, AMBER)
d.text_block(203, 40, 74, [
    "SECURITY POSTURE",
    "",
    "Browser → gateway only;",
    "gateway.ts refuses absolute",
    "URLs (SSRF guard).",
    "",
    "Token is memory-only —",
    "never localStorage; a page",
    "load signs the operator out.",
    "",
    "org_id derived from the",
    "verified token; the client",
    "cannot assert a tenant.",
], size=8.4, lh=5.5)

# 4 — agent theory
d.slide("P2 · Agent", "From prose to evidence: the LangGraph run")
d.bullets(20, 37, 132, [
    "create_run persists MissionState to Redis agent:run:{job_id}",
    "  (24 h TTL) behind a process-local cache — any process may",
    "  execute or poll the run; state is no longer owned by one interpreter.",
    "",
    "Sensor arbitration: cloud forecast blinds optical → SAR primary;",
    "disagreements are published, not hidden (SENSOR_DISAGREEMENT).",
    "",
    "Every node emits fixed server-side narrative events — user or model",
    "free text never enters the stream; the gateway forwards verbatim.",
    "",
    "The mission service polls GET /agent/runs/{id} to terminal state so",
    "jobs and missions never hang in 'running' forever.",
], size=9.6)
d.card(162, 37, 118, 74, GREEN)
d.text_block(167, 42, 110, [
    "LIVE EVENT STREAM (WS)",
    "",
    "connected",
    "status_update PLANNING",
    "SENSOR_DISAGREEMENT",
    "status_update ARBITRATING",
    "ACQUIRING_EVIDENCE",
    "AGENT_THOUGHT …",
    "done (terminal)",
], size=8.8, lh=6.0)

# 5 — ML evaluation
d.slide("P3 · ML", "Measured, not remembered — flood-extent segmentation")
d.bullets(20, 37, 150, [
    "Dataset: Sen1Floods11 — 400 chips, 10 regions; India + Somalia held out.",
    "Why not accuracy: water is 10.8% of pixels — the no-water model scores",
    "  89.2% accuracy with 0.000 IoU. IoU and F1 are the honest metrics.",
    "",
    "Pooled IoU (generated report, fingerprint-checked in CI):",
    "  deterministic Otsu baseline 0.204   flood-unet 0.421",
    "  pretrain 0.407   hand-only-v2 0.435 (pooled F1 0.606)",
    "",
    "Held-out regions generalise (India 0.309 mean IoU vs 0.216 Ghana trained);",
    "the report is regenerated by script — never hand-edited.",
], size=9.6)
d.card(180, 37, 100, 70, RED)
d.text_block(186, 42, 90, [
    "POOLED IoU",
    "",
    "baseline      0.204",
    "flood-unet    0.421",
    "pretrain      0.407",
    "hand-only-v2  0.435",
    "",
    "F1 0.606 · 395/400 chips",
    "scored (abstentions are",
    "excluded, not zeroed)",
], size=8.8, lh=6.0, color=INK)

# 6 — frontend
d.slide("P5 · Frontend", "A console that refuses to lie")
d.bullets(20, 37, 140, [
    "Three-zone shell: query rail | map (the only flexible column) | intel rail;",
    "below 1100 px the rails become drawers so the map stays primary.",
    "",
    "QUERY (red) and PARAMETERS (blue) cards mark planner-inferred fields;",
    "PROGRESS shows only backend-reported stage states — no fake progress bar.",
    "",
    "Map layers: Flood extent, Baseline water, Change, Confidence, AOI;",
    "Before/After/Change scrub rail states that 'dates not published' instead",
    "of inventing a calendar.",
    "",
    "Infrastructure impact reads PostGIS/OSM: roads 2/4 affected (2.46 km),",
    "hospitals 1/3 — linear extent honestly NOT AVAILABLE for point features.",
], size=9.4)
d.card(172, 37, 108, 80, BLUE)
d.text_block(177, 42, 100, [
    "DEMO VS LIVE",
    "",
    "Exactly one module reads",
    "NEXT_PUBLIC_DEMO_MODE",
    "(enforced by test).",
    "",
    "Demo: pinned fixtures,",
    "frozen clock, byte-identical,",
    "Playwright-assertable.",
    "",
    "Live: gateway or nothing —",
    "a failed call never falls back",
    "to fixture data.",
], size=8.6, lh=5.9)

# 7 — live path
d.slide("Engineering", "The live path this week: shared state in Redis")
d.bullets(20, 37, 150, [
    "Defect: run state lived in one process — API-created runs were invisible",
    "  to the poller ('run_not_found'), jobs hung in 'running' forever.",
    "",
    "Fix: agent:run:{job_id} in Redis (24 h TTL) + process-local cache;",
    "  mission jobs poll the agent run endpoint to terminal state;",
    "  dashboard polls /agent/runs/{id} with a bounded 15 s 404 grace window.",
    "",
    "Proven: mission-container process read the agent's run state from Redis;",
    "WS streamed the full envelope chain; job and mission reached honest",
    "terminal failed with 'No observations found to analyze.' locally.",
], size=9.6)
d.card(180, 37, 100, 62, GREEN)
d.text_block(185, 42, 92, [
    "TESTS (this branch)",
    "",
    "vitest        60/60",
    "playwright    20/20",
    "pytest        92 + 2",
    "web build     174 kB",
    "  (budget 180 kB)",
], size=8.8, lh=6.0)

# 8 — closing
d.slide("Demo", "The two surfaces", accent=AMBER)
d.card(20, 37, 126, 86, AMBER)
d.text_block(26, 42, 116, [
    "DEMO  :3010",
    "",
    "Deterministic fixtures; the",
    "Nagaon flood scenario runs",
    "9/9 stages with a DEGRADED",
    "observation stage; confidence",
    "0.87 above gate with three",
    "named uncertainty factors.",
    "",
    "Same build flag, same code,",
    "no hidden second app.",
], size=8.8, lh=6.0)
d.card(154, 37, 126, 86, GREEN)
d.text_block(160, 42, 116, [
    "LIVE  :3002",
    "",
    "Token pasted at /admin",
    "(memory-only by design);",
    "every panel waits for the",
    "gateway — absence renders",
    "NOT AVAILABLE, a failed run",
    "prints the backend's reason.",
    "",
    "Model registry honestly reads",
    "0 models → analyses run the",
    "deterministic baseline, and",
    "the UI says so.",
], size=8.8, lh=6.0)

d.output("SatQuery_Presentation.pdf")
print("SatQuery_Presentation.pdf written,", d.page_no(), "slides")
