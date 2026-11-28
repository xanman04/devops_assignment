# Static Bassline interface

`docker compose up --build` serves these same HTML, CSS and JavaScript files
through stock nginx at http://localhost:8080. There is no UI Dockerfile,
framework or build step. The Assignment 1 Django templates are preserved at the
`archive/a1-monolith` tag.

`config.js` is generated at runtime from `config.js.template` using the public
Discovery and Groups origins. It contains no secrets. Deployments must generate
the same file before publishing to the Azure Storage static website, and configure each API's
`UI_ORIGIN` to that exact UI origin. Never put passwords or tokens in config.

Public routes include `#near`, `#discover?q=...`, `#event/<id>`, `#genre/<slug>`, `#genre/<slug>/<subgenre-slug>` and
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
`#create-event`, `#edit-event/<id>`, `#event-references/<id>`, `#propose-venue`,
`#moderation`, `#notifications`, `#groups`,
`#event-groups/<event-id>`, `#create-group/<event-id>`, `#group/<id>` and
`#edit-group/<id>`. Groups writes validate identity/event facts through Discovery
server-side; the browser does not join databases. A Groups outage leaves public
Discovery usable. Each notification domain reports its own failure separately.

Credentials are opaque, memory-only, expire after 15 minutes, and are discarded
on logout/full reload/current-token 401. Switching routes aborts reads and chat
polling. Late responses from an old credential cannot clear a newer login. A
new login is published only after identity validation. Private DOM is cleared
on session changes. Nothing secret is stored in browser persistent storage.

## Converted pages and limits

The Near me map filters by genre, subgenre and a 7/30-day window, and lists the
artists playing at the events shown. Event organisers (and authorised event
editors) manage the public listening links of an event from My events. The
profile page shows the signed-in person's collection: event cards, the
achievements those cards prove and the remaining locked slots. Attendance
check-in does not exist, so only imported or seeded cards appear; a new account
sees an empty collection. The profile also shows the bio, music links and a genre
chart drawn from the collected cards. Group owners manage bans on the group page, and
moderators review venues and reports.

Image upload and cropping are the deliberately deferred pages (ADR 10), so demo
accounts and groups show no pictures.

Azure publication and read-only desktop/mobile browser checks passed on
November 20 (see [deployment evidence](../AZURE_DEPLOYMENT.md)). Authenticated
participation and both partial-failure cases were verified in production on
November 24 (see [release verification](../RELEASE_VERIFICATION.md)). The map
depends on a third-party renderer and tile provider.
