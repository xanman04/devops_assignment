# Static Bassline interface

`docker compose up --build` serves these same HTML, CSS and JavaScript files
through stock nginx at http://localhost:8080. There is no UI Dockerfile,
framework or build step. The root Django templates remain the Assignment 1
regression reference.

`config.js` is generated at runtime from `config.js.template` using the public
Discovery and Groups origins. It contains no secrets. Deployments must generate
the same file before publishing to the Azure Storage static website, and configure each API's
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
node tools/browser/check_api.cjs
python tools/check_static_ui.py
```

Install the service development requirements first. The checker starts two
real processes with fresh temporary SQLite databases and synthetic accounts,
then uses a real browser for public views, account/profile forms, event
creation/following, private-group request/approval, live chat and responsive
layout. Request regressions also cover stale versus current HTML 401 responses,
gateway failures, 204 responses and provisional identity lookups. It stops its processes afterward.
Screenshots go to ignored `tools/browser/artifacts/`. CI repeats these checks;
the separate Compose job verifies real SQL Server and the container images.
`BROWSER_EXECUTABLE` optionally chooses an installed Chromium browser locally;
`PLAYWRIGHT_CORE_PATH` optionally selects an installed Playwright module.

Authenticated routes include `#login`, `#register`, `#profile`, `#my-events`,
`#create-event`, `#edit-event/<id>`, `#propose-venue`, `#notifications`, `#groups`,
`#event-groups/<event-id>`, `#create-group/<event-id>`, `#group/<id>` and
`#edit-group/<id>`. Groups writes validate identity/event facts through Discovery
server-side; the browser does not join databases. A Groups outage leaves public
Discovery usable. Each notification domain reports its own failure separately.

Credentials are opaque, memory-only, expire after 15 minutes, and are discarded
on logout/full reload/current-token 401. Switching routes aborts reads and chat
polling. Late responses from an old credential cannot clear a newer login. A
new login is published only after identity validation. Private DOM is cleared
on session changes. Nothing secret is stored in browser persistent storage.

This is the core static UI conversion, not complete legacy-page parity. Still
pending: image upload/crop controls, moderator/curation screens, owner listening
reference editing, profile collection/badge displays, ban-management controls,
and richer map date/subgenre filters and nearby-artist browsing. These are
tracked conversion work, not reasons to create small follow-up commits. Azure
publication, live-map network behavior and deployment evidence are unverified.
