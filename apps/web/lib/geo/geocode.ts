/**
 * Place search for the AOI tools (audit F4), via OpenStreetMap Nominatim.
 *
 * This is the one call the browser makes to a host other than the gateway,
 * alongside the basemap tiles. It sends only the text the operator typed and
 * receives public place names and bounding boxes; no token, AOI or mission data
 * leaves the browser. It is allowed in next.config.ts's CSP connect-src.
 *
 * Nominatim's usage policy: at most one request per second, no
 * search-as-you-type, results attributed to OpenStreetMap. The console searches
 * on submit only and enforces the one-second spacing here.
 */

export interface PlaceResult {
  name: string;
  /** [west, south, east, north] in EPSG:4326 */
  bbox: [number, number, number, number];
  center: [number, number];
  kind: string;
}

const ENDPOINT = "https://nominatim.openstreetmap.org/search";
/** Bias results toward India without excluding the rest of the world. */
const INDIA_VIEWBOX = "68.0,37.5,97.5,6.5";

let lastCall = 0;

export class GeocodeError extends Error {}

export function parseNominatim(raw: unknown): PlaceResult[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((r) => {
    if (!r || typeof r !== "object") return [];
    const o = r as Record<string, unknown>;
    const bb = Array.isArray(o.boundingbox) ? o.boundingbox.map(Number) : [];
    const lat = Number(o.lat);
    const lon = Number(o.lon);
    if (bb.length !== 4 || bb.some((x) => !Number.isFinite(x)) || !Number.isFinite(lat) || !Number.isFinite(lon)) {
      return [];
    }
    // Nominatim's boundingbox is [south, north, west, east].
    const [s, n, w, e] = bb as [number, number, number, number];
    return [
      {
        name: typeof o.display_name === "string" ? o.display_name : `${lat.toFixed(3)}, ${lon.toFixed(3)}`,
        bbox: [w, s, e, n] as [number, number, number, number],
        center: [lon, lat] as [number, number],
        kind: typeof o.type === "string" ? o.type : "place",
      },
    ];
  });
}

export async function searchPlace(query: string, signal?: AbortSignal): Promise<PlaceResult[]> {
  const q = query.trim();
  if (q.length < 2) return [];
  const wait = 1000 - (Date.now() - lastCall);
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastCall = Date.now();

  const params = new URLSearchParams({
    q,
    format: "jsonv2",
    limit: "5",
    viewbox: INDIA_VIEWBOX,
    bounded: "0",
    "accept-language": "en",
  });
  let res: Response;
  try {
    res = await fetch(`${ENDPOINT}?${params.toString()}`, {
      signal,
      credentials: "omit",
      referrerPolicy: "strict-origin-when-cross-origin",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new GeocodeError("Place search is unavailable (no connection to OpenStreetMap).");
  }
  if (!res.ok) throw new GeocodeError(`Place search failed (${res.status}).`);
  return parseNominatim(await res.json());
}

/** A rectangle polygon from two opposite corners. */
export function rectanglePolygon(
  a: [number, number],
  b: [number, number],
): { type: "Polygon"; coordinates: number[][][] } {
  const w = Math.min(a[0], b[0]);
  const e = Math.max(a[0], b[0]);
  const s = Math.min(a[1], b[1]);
  const n = Math.max(a[1], b[1]);
  return {
    type: "Polygon",
    coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
  };
}

/** Approximate area of a WGS84 bbox in km² (equirectangular; fine for small boxes). */
export function bboxAreaKm2([w, s, e, n]: [number, number, number, number]): number {
  const mid = (((s + n) / 2) * Math.PI) / 180;
  return Math.abs(e - w) * 111.32 * Math.cos(mid) * Math.abs(n - s) * 110.57;
}

/** A square of `sideKm` centred on a point. */
export function squareAround([lon, lat]: [number, number], sideKm: number) {
  const dLat = sideKm / 2 / 110.57;
  const dLon = sideKm / 2 / (111.32 * Math.cos((lat * Math.PI) / 180));
  return rectanglePolygon([lon - dLon, lat - dLat], [lon + dLon, lat + dLat]);
}

/** Limits that match lib/geo/validate.ts (and the agent's AGENT_MAX_AOI_KM2). */
const PLACE_MAX_KM2 = 2_500;
const PLACE_MIN_KM2 = 4;
/** Side of the box used when a place is too large (or a point) to use as-is. */
const FALLBACK_SIDE_KM = 30;
const POINT_SIDE_KM = 10;

/**
 * Turn a searched place into an AOI the backend will accept.
 *
 * A town or district usually fits and its bounding box is used as-is. A state
 * or country is far over the analysis limit, so a 30 km box around its centre
 * is used instead; a point-like result (a village, a landmark) gets a 10 km box.
 * The note says which happened, so the operator knows to adjust it.
 */
export function aoiForPlace(place: PlaceResult): {
  polygon: { type: "Polygon"; coordinates: number[][][] };
  note: string | null;
} {
  const km2 = bboxAreaKm2(place.bbox);
  if (km2 > PLACE_MAX_KM2) {
    return {
      polygon: squareAround(place.center, FALLBACK_SIDE_KM),
      note: `${place.name.split(",")[0]} is larger than the ${PLACE_MAX_KM2.toLocaleString()} km² analysis limit, so a ${FALLBACK_SIDE_KM} km box around its centre was used. Draw your own area to change it.`,
    };
  }
  if (km2 < PLACE_MIN_KM2) {
    return {
      polygon: squareAround(place.center, POINT_SIDE_KM),
      note: `A ${POINT_SIDE_KM} km box around ${place.name.split(",")[0]} was used.`,
    };
  }
  return { polygon: rectanglePolygon([place.bbox[0], place.bbox[1]], [place.bbox[2], place.bbox[3]]), note: null };
}
