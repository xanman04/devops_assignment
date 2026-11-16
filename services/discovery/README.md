# Discovery service extraction

Run commands in this folder. The service needs only this folder and its pinned
dependencies, with no imports from the root monolith or Groups. It owns an
independent database and exposes JSON only. The original runtime remains a
regression reference during extraction.

## Local operation

Create a virtual environment and install `requirements.txt`. Set
`DJANGO_SECRET_KEY` to a locally generated random secret, then run
`python serve.py`. Startup applies pending migrations before serving with
Waitress. Run `python manage.py createsuperuser` after the first migration to
create a local operator account. Passwords are entered interactively.

`GET /health` returns own-database read/write status and the configured version.
Each request logs method, path, status and duration to stdout. CORS permits only
the configured UI origin. Database/health errors do not expose connection data.

| Variable | Default | Meaning |
|---|---|---|
| DJANGO_SECRET_KEY | Required, secret | Session signing key; never commit a real value |
| DATABASE_URL | sqlite:/// followed by this folder's data/discovery.sqlite3 path | Transitional local database; other schemes currently fail startup |
| ALLOWED_HOSTS | localhost,127.0.0.1,testserver | Comma-separated request hosts |
| UI_ORIGIN | http://localhost:8080 | Sole allowed browser CORS origin |
| PORT | 8000 | Waitress listening port |
| VERSION | development | Git SHA supplied during later packaging/deployment |

## API and identity

`openapi.json` describes all current routes. Public APIs cover genres, approved
venues, map results and event lists/details. Authenticated APIs create/edit
events, follow/unfollow events and read the event-notification inbox.

POST `/api/auth/token/` with a JSON username/password returns an opaque bearer
credential lasting 900 seconds. Send it in `Authorization: Bearer <token>`.
`/api/auth/identity/` checks active/password state on every call. Logout deletes
that credential's session. Expiry and password changes invalidate credentials;
deactivated users receive 403. Credentials never appear in URLs or request logs.
The planned static UI keeps credentials in memory and requires login after a
full reload. Only superusers currently receive the Groups moderation grant;
fine-grained Groups permission migration remains part of Groups extraction.

Use `python manage.py seed_discovery` to load the original curated genre
categories/subgenres without overwriting existing rows. Demo events, performer
media and listening seed commands remain in the monolith pending transfer.

## Verification and remaining work

Install `requirements-dev.txt`, then run the same gates as CI:

```text
python -m ruff check --select E9,F63,F7,F82 .
python -m openapi_spec_validator openapi.json
python manage.py makemigrations --check --dry-run
python -m coverage run --source=discovery,accounts,notifications,config --omit='*/migrations/*,*/test*.py' manage.py test discovery config --noinput
python -m coverage report --fail-under=70
```

The copied domain tests exercise the existing business rules. Tests for the
retired admin/templates remain in the root monolith suite; they are not service
routes. New HTTP tests cover authentication, expiry/revocation, active accounts,
ownership, rejected fields, event writes, inbox isolation, health and CORS.

This is an extraction milestone, not the final submission runtime. SQL Server,
stable-ID data import, containers, the Groups caller, static UI, production login
abuse controls, registration/profile/moderation/reference adapters, full seed
transfer, system.yaml/schema validation and Azure deployment remain pending.
The initial CI workflow tests both runtimes and validates/lints/covers Discovery.
It must later add Groups, SQL Server testing, image builds, system validation
and main-only deployment. No Azure resources or credentials are accessed yet.

November 16 verification found 42 passing service tests and 80% coverage. Lint,
OpenAPI validation and migration-drift checks pass. An isolated-folder startup
applied the schema successfully, then hit Windows socket permission error 10013
while binding Waitress; the live-server restart check remains unverified.
