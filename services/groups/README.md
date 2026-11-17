# Groups service

This independently runnable Django API owns attendance groups, memberships,
requests, bans, messages, notices, history and group notifications. It imports
no Discovery code and never opens Discovery's database. SQLite is transitional
until the SQL Server/container milestone.

## Run and configure

Install `requirements.txt` in a virtual environment, set a randomly generated
`DJANGO_SECRET_KEY`, then run `python serve.py` from this folder. Startup applies
pending versioned migrations before Waitress begins serving. Run Discovery in
its own process first for protected actions and group participation.

| Variable | Default | Purpose |
|---|---|---|
| DJANGO_SECRET_KEY | Required secret | Django runtime signing key |
| DATABASE_URL | sqlite:/// followed by this folder's data/groups.sqlite3 | Own database only; other schemes currently fail startup |
| DISCOVERY_URL | http://localhost:8000 | Peer base URL; no embedded credentials, query or fragment |
| DISCOVERY_TIMEOUT_S | 2 | Positive finite timeout on every peer call |
| PORT | 8000 | Set to a different port, e.g. 8001, when running beside Discovery |
| ALLOWED_HOSTS | localhost,127.0.0.1,testserver | Comma-separated request hosts |
| UI_ORIGIN | http://localhost:8080 | Only permitted browser CORS origin |
| VERSION | development | Git SHA supplied during later deployment |

`openapi.json` describes the current JSON routes. Obtain a bearer credential
from Discovery and send it in the Authorization header. Groups validates it
with Discovery on every protected request, including every chat poll/message.
No passwords, session credentials or permissions are stored in Groups.

Groups stores only account IDs/display-name snapshots in Person records.
Only the current request's validated identity grants moderation privileges.
Historical target references are not independently reauthenticated when an
owner approves/removes another person; that action uses the owner's current
authority. A deactivated target cannot perform protected requests themselves.

## Boundary and failure behavior

Group creation requires an Idempotency-Key header scoped to the authenticated
account. Repeating a key and payload returns the original 201 response; a
different payload returns 409. Replay still requires fresh identity validation
but skips event revalidation. Receipts remain when their group is deleted so
an old retry cannot silently create a replacement group.

Creating/joining/requesting/approving/accepting participation fetches Discovery's
public event details before opening the local membership transaction. The
returned event ID must match and its start must be timezone-aware. Missing
events return 404, cancelled/started events 409, peer failures/malformed data
503, invalid credentials 401 and inactive/unauthorized accounts 403. No client
retry happens inside the HTTP call. Missing internal validation context is a
500 programming error, not a retryable peer failure.

Public group summaries and health use only local data, including during a
Discovery outage. Event title/start are historical snapshots and may be stale.
Chat, leaving, editing, moderation and inbox reads require fresh identity, but
do not fetch event details. Health tests an actual local database read/write.
Logs contain method/path/status/duration and omit credentials and bodies.

The original domain rules are retained, including capacity, one membership per
event, explicit group-switch confirmation, private approval/offers, owner
succession, bans and member-only chat. A database unique constraint on
(event_id, user) supplements the membership checks. Current SQLite IMMEDIATE
transactions serialize local writes. SQL Server needs its own locking and
concurrency verification when that backend is introduced.

## Tests and remaining work

Install `requirements-dev.txt`, then run:

```text
python -m ruff check --select E9,F63,F7,F82 . ../../tools/check_service_boundary.py
python -m openapi_spec_validator openapi.json
python manage.py makemigrations --check --dry-run
python -m coverage run --source=groups,notifications,config --omit='*/migrations/*,*/test*.py' manage.py test config --noinput
python -m coverage report --fail-under=70
```

The test database is data/test_groups.sqlite3, separate from runtime data,
allowing the concurrent-create test to exercise actual SQLite lock behavior.
HTTP adapter tests replace only the network transport with contract-shaped
responses. They assert URL/header/timeout handling, current identity privileges,
event cancellation/missing data, no HTTP while holding a transaction, replay,
concurrent duplicate creation, capacity, switching, approvals, bans and chat.

CI also runs `python tools/check_service_boundary.py` from the repository root.
It starts both real Waitress processes with disposable databases and exercises
identity, event validation, group creation/join/chat, Discovery shutdown,
independent public reads/health, restart and receipt replay. This needs loopback
socket permission; a prior Windows sandbox check was blocked, so live behavior
is verified by the Linux CI job rather than assumed from unit tests.

Remaining work includes SQL Server and existing-data import, complete seed
transfer, containers, static UI, group-photo upload adapters, fine-grained
Groups moderation permission migration, system description/schema and Azure.
Existing photo validation/storage rules are retained in the domain layer;
only existing processed-photo reads are currently exposed over HTTP.
