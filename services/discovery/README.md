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
| DATABASE_URL | sqlite:/// followed by this folder's data/discovery.sqlite3 path | SQL Server mssql:// URL or local SQLite compatibility path |
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

SQL Server and stable-ID data import are implemented. See
[DATA_MIGRATION.md](../../DATA_MIGRATION.md) and ADR 7 for URL/TLS settings,
connection retries, import order, SQL constraints and recovery. Existing admin
audit records are retained in LegacyAdminAudit. Imported Groups permission
grants are returned by the identity endpoint; Groups owns their enforcement.

Standalone SQL Server operation requires Microsoft ODBC Driver 18.
SQLSERVER_TEST_MODE=1 selects the destructive local-only runner for disposable
sqlserver/localhost/127.0.0.1 databases. Never use it on application data.

Container orchestration, static UI, production login abuse controls, remaining
registration/profile/moderation/reference adapters, complete seed transfer,
system.yaml/schema validation and Azure deployment remain pending. The current
CI has service/monolith and HTTP-boundary checks; SQL Server/image gates follow
in the container milestone. No Azure credentials are used by these tests.
