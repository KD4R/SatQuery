/**
 * Copy MapLibre's web-worker modules into public/ (runs before dev and build).
 *
 * maplibre-gl v6 locates its worker next to its own module file
 * (import.meta.url). Once Next bundles maplibre into a chunk, that sibling file
 * does not exist, the worker never starts, and every GeoJSON layer (the AOI
 * outline, the measured water polygons, the demo change polygons) silently never
 * renders while raster tiles still do. MapWorkspace points maplibre at these
 * copies with setWorkerUrl(). They are generated, so they are gitignored and
 * always match the installed maplibre version.
 */
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const dist = dirname(require.resolve("maplibre-gl/dist/maplibre-gl.css"));
const out = join(here, "..", "public", "vendor", "maplibre");
mkdirSync(out, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(dist, f), join(out, f));
}
process.stdout.write(`maplibre worker copied to ${out}\n`);
