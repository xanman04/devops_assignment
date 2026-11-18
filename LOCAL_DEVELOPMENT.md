# Local container stack

From a clean clone, with Docker running, start everything with:

```text
docker compose up --build
```

Open http://localhost:8080. It currently serves the static UI shell; the full
browser workflows are the next milestone. Discovery is at localhost:8000 and
Groups at localhost:8001. Each service has GET /health. The root Django app
remains the Assignment 1 reference during UI migration.

The stack has exactly two domain service images/Dockerfiles. SQL Server is a
stock 2022 image with two databases. The static file server is stock nginx with
the ui/ folder mounted. A stock Python bootstrap helper creates local secrets
and exits; the one-off stock SQL Server helper initializes databases/logins and
exits. Neither helper is another application service or deployed Azure resource.
On Apple Silicon, enable Docker Desktop's Rosetta emulation for the amd64 SQL
Server image. The tested platform is Linux amd64 via Docker Desktop on Windows.

## Secrets, data and configuration

No real password or .env file is needed in the clone. A bootstrap helper creates
random credentials once in separate Docker volumes, with private file modes.
The SQL administrator credential is mounted only into SQL Server and its setup
helper. Each app sees only its own database password and Django secret. Values
are loaded at runtime and never copied into images or printed. Local SQL
connections are encrypted with a self-signed certificate exception. Azure must
instead supply validated TLS connections and platform secret references.

SQL Server stores both databases in sqlserver-data. Each service has a separate
data volume for uploaded files. Named secrets/data volumes survive container
recreation. Stop with `docker compose down`; restart with the normal up command.
Never delete volumes to deploy or to get a migration/import passing.

Database bootstrap is idempotent and does not reset existing users/passwords.
Schema migrations apply before serving, with a schema lock. A second boot
applies no migrations. Discovery taxonomy seeding is repeatable and keeps
existing edits. The app users have read/write/DDL rights only in their own DB,
and tests verify that the other database cannot be read.

| Local variable | Default | Purpose |
|---|---|---|
| DISCOVERY_PORT | 8000 | Host loopback port for Discovery |
| GROUPS_PORT | 8001 | Host loopback port for Groups |
| UI_PORT | 8080 | Host loopback port and browser CORS origin |
| VERSION | development | Version exposed by health; CI/CD later supplies Git SHA |

Compose sets LOCAL_SECRETS_DIR, DATABASE_HOST/NAME/USER and the peer/UI URLs.
Standalone service variables are listed in each service README and
DATA_MIGRATION.md. IMPORT_SPLIT_DATA optionally names a privately mounted
first-import file. SEED_TAXONOMY controls startup taxonomy seeding. Do not
import after the target has been seeded or otherwise populated; follow the
offline first-import sequence in DATA_MIGRATION.md.

The nginx entrypoint renders public API URLs from environment variables into
/tmp/config.js. The same static source files can later be deployed to Static
Web Apps with deployment-generated configuration. API base URLs belong in
configuration, not application JavaScript literals.

## Operating a single service

Start SQL Server and bootstrap first, then the desired app:

```text
docker compose up -d sqlserver
docker compose up --no-deps --exit-code-from db-init db-init
docker compose up --build discovery
```

Groups can run independently with its own health/public reads, while protected
actions require Discovery. Create an operator account interactively using
`docker compose exec discovery python manage.py createsuperuser`. New-clone
SQL databases contain taxonomy, not copied user data or preconfigured accounts.
Existing private records are never transferred automatically.

## Verification

Run `python tools/check_compose.py --project bassline-check-local`. It builds
both images and uses a separate project/volumes with disposable synthetic data.
The checker deliberately rejects ordinary project names because its explicit
SQLSERVER_TEST_MODE runner flushes the test databases. It never accesses Azure.

The checks cover restricted SQL logins, both service suites and coverage gates,
in-place migration preservation, duplicate-create concurrency, non-root runtime,
UI/config serving, create/join/chat HTTP flow, restart with unchanged migration
history and retained messages, and Discovery outage behavior. Containers are
stopped/removed afterward and volumes are retained for inspection. The regular
development project and its data are separate. Do not rename a personal-data
project to match the checker's disposable project prefix.

GitHub Actions repeats this SQL Server/Compose check on every push and PR,
alongside the root regression and service lint/OpenAPI/coverage gates. Image
publication, Azure deployment and system.yaml/schema validation remain later
milestones. All database testing is local or on the GitHub runner.
