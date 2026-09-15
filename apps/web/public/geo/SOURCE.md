# `public/geo/land-50m.json`

Land polygons at 1:50m, TopoJSON. Extracted from the `world-atlas` npm package
(ISC), which packages **Natural Earth** vector data.

Natural Earth is released into the **public domain** — no permission, fee or
attribution is required, though it is offered here anyway.

- Natural Earth: https://www.naturalearthdata.com
- world-atlas: https://github.com/topojson/world-atlas

It is vendored as a static asset rather than pulled in as a dependency because the
landing page fetches it at runtime from its own origin; the browser is not permitted
to call any host but the gateway, and a build-time import would put 545 KB of
geometry into the JS bundle.

To refresh: `npx --yes world-atlas@2` or copy `node_modules/world-atlas/land-50m.json`.
