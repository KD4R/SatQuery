"use client";

/**
 * Step 1 · Where: find the place, then set the area of interest.
 *
 * Search (OpenStreetMap Nominatim, on submit only) flies the map to the place.
 * The area can then come from the place itself ("Use this place") or be drawn
 * on the map as a rectangle or polygon. The current AOI, its size and whether it
 * is valid are always shown here, so the rail says what will be analysed.
 *
 * In demo mode the AOI is pinned to the demo scene; search still moves the map,
 * but the area cannot change, and the panel says so.
 */

import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { Crosshair, MapPin, PenLine, Search, Square, X } from "lucide-react";

import { formatArea } from "../../lib/geo/format";
import { aoiForPlace, GeocodeError, searchPlace, type PlaceResult } from "../../lib/geo/geocode";
import type { ValidationResult } from "../../lib/geo/validate";
import type { GeoJSONPolygon } from "../../lib/api/types";

export interface WherePanelHandle {
  focusSearch: () => void;
}

export const WherePanel = forwardRef<
  WherePanelHandle,
  {
    demo: boolean;
    aoi: GeoJSONPolygon | null;
    aoiLabel: string | null;
    validation: ValidationResult;
    locked: boolean;
    onFlyTo: (bbox: [number, number, number, number]) => void;
    onSetAoi: (aoi: GeoJSONPolygon | null, label: string | null) => void;
    onDraw: (mode: "rectangle" | "polygon") => void;
  }
>(function WherePanel({ demo, aoi, aoiLabel, validation, locked, onFlyTo, onSetAoi, onDraw }, ref) {
  const input = useRef<HTMLInputElement | null>(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<PlaceResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [place, setPlace] = useState<PlaceResult | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useImperativeHandle(ref, () => ({ focusSearch: () => input.current?.focus() }), []);

  const search = async () => {
    setError(null);
    setResults(null);
    setBusy(true);
    try {
      const found = await searchPlace(q);
      setResults(found);
      if (found.length === 0) setError("No place found. Try a district or town name.");
    } catch (caught) {
      setError(caught instanceof GeocodeError ? caught.message : "Place search failed.");
    } finally {
      setBusy(false);
    }
  };

  const choose = (p: PlaceResult) => {
    setPlace(p);
    setResults(null);
    setNote(null);
    setQ(p.name.split(",")[0] ?? p.name);
    onFlyTo(p.bbox);
  };

  const usePlace = () => {
    if (!place) return;
    const r = aoiForPlace(place);
    setNote(r.note);
    onSetAoi(r.polygon, place.name.split(",").slice(0, 2).join(","));
  };

  const errors = validation.findings.filter((f) => f.severity === "error" && f.rule !== "aoi.missing");
  const areaEditable = !demo && !locked;

  return (
    <section className="sqd-card sqd-where" aria-label="Where" id="step-where">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">
          <MapPin size={13} /> 1 · Where
        </span>
        {aoi ? (
          <span className={`sqd-chip ${validation.valid ? "is-ok" : "is-danger"}`}>
            {validation.valid ? "Area set" : "Area invalid"}
          </span>
        ) : (
          <span className="sqd-chip">No area yet</span>
        )}
      </header>

      <form
        className="sqd-search"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
      >
        <Search size={14} aria-hidden="true" />
        <input
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search a place — e.g. Nagaon, Assam"
          aria-label="Search a place"
          autoComplete="off"
        />
        <button className="sqd-btn" type="submit" disabled={busy || q.trim().length < 2}>
          {busy ? "…" : "Search"}
        </button>
      </form>

      {results && results.length > 0 ? (
        <ul className="sqd-results" role="listbox" aria-label="Places found">
          {results.map((r) => (
            <li key={`${r.center[0]},${r.center[1]}`}>
              <button type="button" role="option" aria-selected={false} onClick={() => choose(r)}>
                <b>{r.name.split(",")[0]}</b>
                <small>{r.name.split(",").slice(1, 4).join(",").trim() || r.kind}</small>
              </button>
            </li>
          ))}
          <li className="sqd-results-credit">Search © OpenStreetMap contributors</li>
        </ul>
      ) : null}
      {error ? (
        <p className="sqd-note is-warn" role="status">
          {error}
        </p>
      ) : null}

      <div className="sqd-aoi-tools" role="group" aria-label="Area of interest">
        <button className="sqd-btn" type="button" onClick={usePlace} disabled={!place || !areaEditable}>
          <Crosshair size={13} /> Use this place
        </button>
        <button className="sqd-btn" type="button" onClick={() => onDraw("rectangle")} disabled={!areaEditable}>
          <Square size={13} /> Rectangle
        </button>
        <button className="sqd-btn" type="button" onClick={() => onDraw("polygon")} disabled={!areaEditable}>
          <PenLine size={13} /> Polygon
        </button>
        {aoi && areaEditable ? (
          <button
            className="sqd-btn"
            type="button"
            onClick={() => {
              setNote(null);
              onSetAoi(null, null);
            }}
            aria-label="Clear area"
          >
            <X size={13} />
          </button>
        ) : null}
      </div>

      <dl className="sqd-facts sqd-aoi-facts">
        <div>
          <dt>Area</dt>
          <dd>{aoi ? (aoiLabel ?? "Drawn on the map") : "—"}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{aoi ? formatArea(validation.areaSqM) : "—"}</dd>
        </div>
      </dl>
      {note ? <p className="sqd-note">{note}</p> : null}
      {errors.map((f) => (
        <p key={f.rule} className="sqd-note is-danger">
          {f.message}
        </p>
      ))}
      {demo ? (
        <p className="sqd-note">
          Demo mode: the area is pinned to the demo scene. Search still moves the map; in live mode the
          area follows what you choose here.
        </p>
      ) : null}
    </section>
  );
});
