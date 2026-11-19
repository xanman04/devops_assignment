# Static Bassline interface

`docker compose up --build` serves these same HTML, CSS and JavaScript files
through stock nginx at http://localhost:8080. There is no UI Dockerfile,
framework or build step. The root Django templates remain the Assignment 1
regression reference.

`config.js` is generated at runtime from `config.js.template` using the public
Discovery and Groups origins. It contains no secrets. Deployments must generate
the same file before publishing to Static Web Apps, and configure each API's
`UI_ORIGIN` to that exact UI origin. Never put passwords or tokens in config.

Public routes include `#near`, `#discover?q=...`, `#event/<id>`, `#genre/<id>` and
`#artist/<id>`. The map renderer is pinned to MapLibre 6.3.0 and uses OpenFreeMap;
network/WebGL failure leaves an ordinary event list. Artwork and the Funnel
Display font are bundled; their existing licenses and `DJ_SOURCES.md` apply.
All external music links open on their provider's site.

Browser checks are development tools, outside the deployed `ui/` directory:

```text
npm ci --prefix tools/browser
npx --prefix tools/browser playwright install chromium
python tools/check_static_ui.py
```

Install the service development requirements first. The checker starts two
real processes with fresh temporary SQLite databases and synthetic accounts,
then uses a real browser for routing, search, safe text, detail/genre/artist
views, map failure and responsive layout. It stops its processes afterward.
Screenshots go to ignored `tools/browser/artifacts/`. CI repeats these checks;
the separate Compose job verifies real SQL Server and the container images.
`BROWSER_EXECUTABLE` optionally chooses an installed Chromium browser locally;
`PLAYWRIGHT_CORE_PATH` optionally selects an installed Playwright module.

This public milestone does not yet convert account forms, moderation or group
participation. Those routes remain the next coherent UI workstream. It also
does not prove Azure publication, live map-tile availability or feature parity
with every legacy page.
