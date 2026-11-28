# Data migration and recovery

The two services support SQL Server through mssql-django 1.8.0, pyodbc 5.3.0
and Microsoft ODBC Driver 18. SQLite remains available for quick compatibility
checks. The submitted deployment must use one serverless Azure SQL database
per service. The backend reference is the [Microsoft repository](https://github.com/microsoft/mssql-django/tree/1.8.0).

## Connection and schema rules

Set DATABASE_URL privately using the shape
`mssql://<percent-encoded-user>:<percent-encoded-password>@<host>:1433/<database>`.
TLS certificate validation is enabled. Only a local self-signed SQL Server
uses `?trust_server_certificate=yes`. Never use that exception for Azure.
Driver login attempts use a five-second timeout, ten transient retries with
five-second backoff, and a thirty-second query timeout. This includes the
backend's transient 40613 database-resume handling. Authentication/configuration
errors are not treated as arbitrary endlessly retryable errors.

Startup applies migrations under a database-scoped session lock. Group domain
writes take a separate transaction-owned application lock before reading
mutable membership state. An unprotected caller-owned transaction is rejected.
The lock never spans a peer HTTP request. SQLite uses BEGIN IMMEDIATE instead.

SQL Server does not support the two existing LOWER-expression unique indexes.
They are redundant there under the required case-insensitive collation and the
ordinary unique name / category-name keys. Tests verify case-only duplicate
rejection at the database level. The backend's W044 warnings remain visible.
An in-place URL digest backfill preserves DJ recording links while avoiding
SQL Server's maximum index-key width. The nullable notification-request key
uses a filtered unique constraint so unrelated NULL-source notifications can
coexist.

## First-time split of an existing database

1. Stop writes to the source app and keep a private backup of its SQLite file
   and uploaded files. Run the source command from the repository root:
   `python manage.py export_split_data data/exports/assignment1.json`.
   The command takes a consistent read snapshot and refuses to overwrite a
   file. Output must be under the configured DATA_DIR (ignored data/ by default).
2. Treat that export as sensitive. It contains password hashes, emails and chat
   records. Never commit, publish or attach it to CI artifacts. Use only trusted
   local copies. No live session credentials are exported.
3. Initialize the two new databases/logins, apply each service's migrations, and
   leave the services offline. Do not seed or create accounts first. The target
   must be empty apart from generated Django metadata and a health probe.
4. From each service folder, with its own DATABASE_URL configured, run
   `python manage.py import_split_data <private-export-path>`.
   The importer accepts only that owner's models. User/event/group/message IDs
   stay stable. Generated metadata and role references use natural keys rather
   than environment-dependent numeric IDs. The entire import and fingerprint
   marker commit together. Retrying the same export is a no-op. A different
   export or any pre-existing owned data causes refusal, not replacement.
5. Copy account avatars/event uploads into Discovery's media root and group
   photos into Groups' media root. Retain their existing relative paths. The
   import transfers file references, not bytes.
6. Verify counts, stable IDs, sign-in/role grants, event/group relationships,
   chat and both notification inboxes. Then run repeatable taxonomy seeding
   and resume traffic. Keep the original source untouched until verified.

Once container setup is available, IMPORT_SPLIT_DATA can point to a privately
mounted export during startup, before the optional SEED_TAXONOMY step. Do not
put an export into an image. If the target is already populated, stop and plan
reconciliation. Never delete a volume or recreate a database to make import fit.

`python tools/check_split_import.py` verifies the complete source-export and
two-import path with synthetic disposable SQLite data, including role grants,
passwords, owner transfer, chat and notification separation. Service tests also
exercise import and identity sequences on local SQL Server.

## Verification and production recovery

SQLSERVER_TEST_MODE=1 enables an explicit destructive test runner only on
sqlserver/localhost/127.0.0.1. It migrates and flushes the configured local DB,
using its restricted owner login without creating extra databases. Enable it
only in disposable test stacks. The guard rejects remote Azure hosts. Ordinary
CI and local verification never connect to Azure SQL.

For a failed production migration, stop deployment and preserve its logs and
backup position. Prefer a new forward corrective migration. Never edit applied
files, mark a failed migration as applied, or reset the database on deployment.
Irrecoverable loss requires professor-coordinated backup recovery that respects
the two-database quota. Recheck retained records before restoring traffic.

## Populated-table migration on Azure: GenreCategory.slug

The second-stage migration is `discovery` 0014 and 0015, applied by the normal
deployment to the 22 genre categories already stored in Azure SQL:

1. 0014 adds `slug` as a nullable, non-unique column and backfills every existing row
   with a readable unique key derived from its name (`Dubstep / 140` becomes
   `dubstep-140`; a collision gets `-2`, `-3`). IDs, names and all other columns are
   not touched. The data step is forward-only.
2. 0015 then makes `slug` required and unique, after no row can violate it.

Splitting the steps keeps each schema change small and lets a failure after step 1 be
fixed with a corrective forward migration. New and renamed categories keep their slug
(`GenreCategory.save` fills it once); `import_split_data` derives slugs for imported
rows because raw fixture saves skip `save()`. The UI links genres as `#genre/<slug>`
and the API serves `GET /api/genres/slug/{genre_slug}/` next to the numeric route.

`discovery/test_migrations.py::GenreSlugMigrationTests` migrates a populated test table
from 0013 to the latest state and checks ids, names and other columns are unchanged and
slugs are unique. Local tests do not replace the Azure evidence: the "before" snapshot
is `evidence/azure/2026-11-23-before-slug-migration.json`; the "after" snapshot, the
startup migration log and the deployment run link are added once the deployment ran.

## Second populated-table migration on Azure: GenreTag.slug

`discovery` 0017 and 0018 repeat the pattern on a larger populated table, the 251
subgenres in `discovery_genretag`. 0017 adds a nullable `slug` column, backfills every
row in primary-key order and prints the row count into the startup log; a name used
under two genres gets a numeric suffix. 0018 makes the column required and unique.
IDs, names, categories, descriptions and tempo ranges are not touched. New subgenres
get a slug from `GenreTag.save`, `import_split_data` derives slugs for imported rows,
and the genre page opens one subgenre at `#genre/<genre-slug>/<subgenre-slug>`.

This migration was added on November 28 partly so that Azure startup output could be
captured while it ran, because the console output of 0014/0015 was not kept. It is a
separate migration and its log is not evidence about the November 23 one. The change
was rehearsed first on a local SQL Server database populated by the previous version.
`evidence/azure/2026-11-28-before-subgenre-slug.json` holds the live rows before
deployment; the rows afterwards and the captured startup output are stored beside it
once the deployment has run.
