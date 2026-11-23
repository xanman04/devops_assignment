# Bassline Assignment 2 — Claude handoff

Prepared November 20, 2026, after the first successful Azure deployment.
This records verified state and open work; it does not claim the assignment is done.

## Start here

1. Read [AGENTS.md](AGENTS.md), then [COMMIT_TIMELINE.md](COMMIT_TIMELINE.md).
   The timeline contains the 11-commit ledger, observed remote evidence, remaining
   November 21–22 blocks, and the strict commit/disclosure policy.
2. Work in **`C:/School/devops/individual_assignment/devops_assignment2`**.
   It is an independent local checkout of the **same remote history**:
   `https://github.com/xanman04/devops_assignment.git`.
3. `devops_assignment1` is intentionally detached at recorded A1 baseline
   `33bf6d10fa11cfb9a63586dcb4ab2fb33eb8d384`. Do not implement A2 there,
   switch it to remote main, rewrite history or create a separate submission repo.
   The old `devops_assignment1.git` remote URL redirects to the canonical repo.
4. Recheck current branch/status/main/Actions before acting: this is a dated snapshot.
   At handoff, both source checkouts were clean. The docs added by this handoff
   turn will be uncommitted and must join the next substantial milestone.
5. Source brief: local `Assignment_2.pdf` (excluded locally from Git). Updated
   authority: `C:/School/devops/class_content/a2-azure-deployment-guide.pdf`.
   The November 20 guide supersedes the old class-group/Static Web App instructions.

## Owner's non-negotiable automatic-commit policy

**LESS IS MORE. Never repeat Assignment 1's roughly 170 commits and handwritten
own-words backlog. A prompt, file edit, tool call, review reply or small fix is
not a commit trigger.**

- Implementation work is automatically committable only at completed, substantial,
  cohesive milestones. Name the overarching outcome first. Batch its code, tests,
  review fixes, infrastructure, documentation and factual AI log together.
- One AI_USAGE row per coherent commit, grouping all related prompts/tools/agents.
  Do not create per-prompt rows. Keep the existing columns and historical A1 rows.
  **Only the owner writes “In my own words”; leave it pending until supplied.**
- The owner explicitly accepted this grouped interpretation of “meaningful
  interaction”; it is not claimed to be professor-approved. Disclose it honestly.
- Aim near the 12-commit minimum. The current forward plan is 12–13 total if work
  permits; never split a milestone or invent another to hit an illustrated schedule.
- Do not make a commit just for this handoff, a map one-liner, a hash, a log row,
  a screenshot or a small correction. Intermediate changes may remain in the tree.
- Automatic commits/pushes/PR merges are authorized within active implementation
  scope. Planning-only requests stay planning-only. There is no background timer.
- Verify staged content, branch and remote. Feature branch → push → PR → exact-head
  CI → merge preserving commits → exact-main-SHA CD. No direct-main implementation,
  squash/rebase collapse, force-push or published-history rewriting.
- Report failures, untested behavior and uncommitted work. End meaningful turns
  with a short `State:` paragraph. See AGENTS for permission and MC/1 review rules.

## Verified Git and deployment state

| Item | Verified value |
|---|---|
| Local branch at handoff | `main` |
| Main and deployed SHA | `181474919a9451414fd6a6087e6d681c8a737c0a` |
| Latest substantive commit | `c96f8d836cf9ffffbd72b2703d4d0f2da0b0ecc4` — Launch and verify the student Azure deployment |
| Latest merged PR | [PR 9](https://github.com/xanman04/devops_assignment/pull/9), November 20 14:35:36 Paris |
| Current successful main CD | [44745670962](https://github.com/xanman04/devops_assignment/actions/runs/44745670962), completed November 20 14:41 Paris |
| First actual Azure CD / baseline stage | [44742390475](https://github.com/xanman04/devops_assignment/actions/runs/44742390475), SHA `7bd8ba217b4ac9216bee99860c6c076c958de595` |
| UI | https://xcieu2023ui.z1.web.core.windows.net/ — working Discovery route `/#discover` |
| Discovery API | https://xc-ieu2023-discovery.ashypebble-7eb9f1b0.germanywestcentral.azurecontainerapps.io |
| Groups API | https://xc-ieu2023-groups.ashypebble-7eb9f1b0.germanywestcentral.azurecontainerapps.io |
| Process count | 11 substantive A2 commits across six calendar dates; merge commits excluded |
| Tags | None found during November 20 verification; check again before creating `submission` |

PR 9's 12 push/PR checks passed. Main's own same-SHA CI, two image publications
and deployment passed. Both deployed `/health` endpoints returned 200, `db: ok`,
and the full current main SHA. Read-only browser checks confirmed Discovery
desktop/mobile rendering, distinct API addresses, browser-origin CORS, no JS
exceptions and no mobile horizontal overflow. These checks do **not** cover
authenticated production participation or the default map layout.

All 22 seeded genre category IDs/names survived the second deployment unchanged.
Initial public-data snapshot:
[`evidence/azure/2026-11-20-initial-deployment.json`](evidence/azure/2026-11-20-initial-deployment.json).
There are **zero public events** in the initial Azure deployment. No demo/operator
account was automatically created. The snapshot is not a SQL backup.

## What is implemented

- Two independent Django services/processes/images under `services/discovery/`
  and `services/groups/`, with pinned manifests and non-root Dockerfiles.
- Discovery owns credentials/accounts, venues/events, taxonomy, artists/listening,
  follows and event notifications. Groups owns credential-free person references,
  attendance groups/membership/requests/chat and group notifications. Every table
  has one owner. No shared database access or cross-domain foreign keys.
- Protected Groups requests validate identity through Discovery HTTP; creation/join
  also checks event eligibility server-side before local transactions. Peer URLs
  are configured, every call has a timeout, and failures have explicit statuses.
  The UI → Groups → Discovery seam is tested locally, not yet demonstrated live.
- Opaque memory-only browser bearer sessions expire after 900 seconds. Passwords
  remain in Discovery. Session races, database-backed login throttling, and trusted
  Azure proxy handling have local regression coverage.
- SQL Server support, ordered automatic Django migrations and database-scoped
  migration locks; split-export/import preserves stable IDs and resolves permission
  metadata naturally. Existing migrations must not be edited or faked.
- Local Compose: two domain images, SQL Server 2022, one-off init/bootstrap and
  stock nginx serving the same `ui/` files. Separate local DBs/users/credentials,
  persistent volumes; no UI Dockerfile or third domain service.
- Static UI: public map/list/browse/search/event/genre/artist projections; core
  registration/login/profile; event create/edit/cancel and venue proposal; follows,
  reports, inboxes; group forms/join/request approval/switch/leave/delete, member
  controls and polling chat. Remaining parity is listed below.
- Versioned OpenAPI documents, official `system.schema.json` unchanged,
  `system.yaml`, and CI schema/path/env-read/peer-operation validation.
- CI: monolith regression reference; service lint/OpenAPI/migration drift and
  per-service 70% coverage; real HTTP boundary/browser tests; real local SQL Server
  Compose/build/isolation/restart/outage checks; Terraform mock/provider checks.
  CI **never** uses Azure SQL.
- Main-only serialized CD after same-SHA CI; public full-SHA GHCR images;
  Terraform private state/plan guards; Storage UI configuration/upload; bounded
  exact-version health checks. The root monolith still exists as A1 reference.

## Azure — already set up; do not repeat activation/provisioning blindly

- Account: `xc.ieu2023@student.ie.edu`; prefix `xc-ieu2023`.
- Active **Azure for Students** subscription:
  `f940692d-0846-474b-83cb-9bac90f33adf`; tenant
  `4a39c578-6df0-42b9-a7e0-e9eac6d91816`. Activation was verified Enabled,
  with the portal showing $100 credit. This is not a current remaining-cost audit.
- **Do not use IE Workspaces**, the Enterprise Agreement/group-project subscription
  `5841fd26-0b2d-4bd0-8dcb-40add3353593`.
- Policy-allowed regions observed: Belgium Central, Germany West Central, Italy
  North, Norway East, Switzerland North. Current compute and SQL use
  **`germanywestcentral`**; the student free offer succeeded there.
- Own group `rg-xc-ieu2023`; identity `xc-ieu2023-github`; Storage `xcieu2023ui`;
  environment `xc-ieu2023-env`; logs `xc-ieu2023-logs`; server `xc-ieu2023-sql`;
  apps `xc-ieu2023-discovery` / `xc-ieu2023-groups`; DBs
  `xc-ieu2023-discovery-db` / `xc-ieu2023-groups-db`.
- Exactly two Consumption apps configured min 0/max 1, one environment, two domain
  DBs on one SQL server, and one UI/state Storage account. SQL `master` is an
  unavoidable system database, not a third domain database.
- Actual SQL settings verified: Gen5 serverless 0.5–1 vCore, `useFreeLimit=true`,
  exhaustion `AutoPause`, 60-minute pause, offer-controlled 32 GiB, Local backups.
  Never override pause/size or silently allow paid overflow. Storage/logs meter
  usage; scale-to-zero is not a promise that every resource is literally free.
- Private state container `xc-ieu2023-tfstate`, separate from `$web`, Azure AD
  authentication and shared keys/public blob ACLs disabled. Never expose state,
  plans, DB passwords or credentials in Git, artifacts or chat.
- Identity Contributor is scoped to this group only; Blob Data Contributor to
  this Storage account. Named and numeric repository subjects trust main only.
  Both professors have Reader access. No class SP secret or SWA token is needed.
- GitHub secret names: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
  `AZURE_SUBSCRIPTION_ID`, `SQL_ADMIN_PASSWORD`, `DISCOVERY_DB_PASSWORD`,
  `GROUPS_DB_PASSWORD`, `DISCOVERY_SECRET_KEY`, `GROUPS_SECRET_KEY`.
  They are already configured; values are not retrievable from GitHub and must
  not be requested in chat. Variables include prefix/group/storage/regions and
  `AZURE_DEPLOYMENT_READY=true`.
- Both GHCR packages are **public**. Owner explicitly refreshed CLI access with
  `read:packages`. Do not repeat that permission request without a fresh failure.
- Actual deployment verified each contained user could access its own database
  and was denied the other domain database. The temporary runner-IP SQL firewall
  rule was removed; only the prescribed Azure-services exception remained.
- Leave ingress CORS off; application middleware restricts the browser origin.
  After documented initial setup, infrastructure/configuration changes go through
  the pipeline. Do not use manual portal fixes or rerun bootstrap as routine CD.
- The lecture's “manual infrastructure” preference is met through explicit,
  explainable Terraform. It does not authorize VMs, App Service, AKS, brokers,
  always-on compute or substitution of the required services.

## Open runtime work and known map regression

**Default `Near me` map is currently broken visually; do not claim it passed.**
The external MapLibre stylesheet's `.maplibregl-map` rule overrides the static
`.ui-map` positioning. The map container measures 0px high even though the canvas,
style request and JS load. The list and Discovery route remain usable.

The isolated fix is changing the selector in `ui/ui.css` from
`.ui-map {position:absolute;...}` to
`.ui-map-page > .ui-map {position:absolute;...}`. This restores specificity without
redesigning the interface. It was visually verified in a production-page preview
with only CSS overridden: 1000px map height and visible Madrid tiles.

- Ignored local patch: `.tools/map-layout-fix.patch` (passes `git apply --check`).
- Actual failing capture: `tools/browser/artifacts/live/near-desktop.png`.
- Preview-only fixed capture: `tools/browser/artifacts/live/near-map-fix-preview.png`.
- **Patch is not applied to tracked source, committed or deployed.** These ignored
  artifacts do not travel with a fresh clone; the exact selector change is above.
- Batch it into the next substantive UI/runtime milestone. Extend live checks
  to verify map container dimensions with the real external stylesheet loaded;
  the existing offline fallback fixture did not catch this CSS interaction.

Other pending A1 UI conversion: upload/crop controls and persistent Azure media,
moderator/curation screens, owner listening-reference editing, profile collections
and badges, ban management, richer map date/subgenre filters and nearby artists.
Inspect the actual A1 workflows/brief to determine required parity and priority;
do not silently declare them all optional or invent new product features.
ACA local `/app/data/media` is ephemeral: existing APIs alone do not establish
persistent uploaded-media hosting. Resolve storage within the updated contract.

## Evidence and submission work still open

1. **A later migration of an already populated Azure table.** The first Azure boot
   already applied existing backfills, so those are not proof of the required
   second-stage preserving migration. Choose a useful real change, capture the
   current rows before deploying it, then capture retained IDs/rows, startup
   migration log and run URL. Never recreate/drop DBs or edit applied migrations.
2. Demonstrate an authenticated user-visible UI → Groups → Discovery flow on
   Azure. Plan secure operator/approved-venue initialization if needed: there is
   no seeded administrator. Do not publish a known default admin password.
3. Demonstrate partial failure on Azure: stop one service through reproducible
   pipeline-controlled configuration, show the other domain still working and
   the affected flow's clear error, then restore it. Local Compose tests already
   cover outage/isolation, but do not substitute those for claimed Azure evidence.
4. Cold starts/full SQL auto-pause resume have not been demonstrated live. Preserve
   bounded retries/startup locks and record actual behavior rather than guessing.
5. Exactly ADRs 6–10 are required. 6–9 exist; add **10**, justify a real deferred
   capability and its trigger. Their three-date requirement is already covered.
6. Finish accurate docs and a 4–5 page report: before/after architecture, deployment
   flow/names, per-domain DB diagrams, Azure migration and failure evidence,
   successful main CD link and syllabus AI disclosure. Preserve author ownership.
7. A **genuine failed-and-fixed CI/CD run** has not been found. The November 20
   initial setup encoding failure was local; run 44741411495 was canceled before
   deployment during checkout clarification. Neither is a failed CI/CD proof.
   Do not manufacture a failure or mislabel cancellation. Flag this requirement
   to the owner and document any real failure/correction that occurs.
8. Owner explanations remain pending for the 11 grouped A2 AI rows. Teach/review
   in manageable workstream groups now; agents must not fill these as the owner.
9. Reconcile actual A1 submitted baseline, process/push evidence and all brief
   requirements. Check final deployed full SHA, then create/push `submission`
   without overwriting an existing tag. Submit matching repo/full SHA/live URL
   and report by November 22 23:59. Keep live until grades are published.
10. The written comprehension check multiplies the grade. Explain the real code,
    infrastructure, tradeoffs and test limits throughout implementation.

## Files and tools to use

| Purpose | Files |
|---|---|
| Required rules / schedule | `AGENTS.md`, `COMMIT_TIMELINE.md`, this file |
| Architecture / decisions | `SERVICE_BOUNDARIES.md`, `ADR.md`, `DATA_MIGRATION.md` |
| Local stack / UI limits | `LOCAL_DEVELOPMENT.md`, `docker-compose.yml`, `ui/README.md` |
| Azure procedure | `AZURE_DEPLOYMENT.md`, `infra/README.md`, `infra/*.tf` |
| Pipeline / deploy | `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `tools/deploy_azure.py` |
| Setup / SQL / guards | `tools/azure_preflight.py`, `tools/azure_bootstrap.py`, `tools/initialize_azure_sql.py`, `tools/deployment_guard.py` |
| Contracts / inventory | `system.schema.json`, `system.yaml`, `tools/check_system.py`, service `openapi.json` files |
| Evidence / disclosure | `evidence/azure/2026-11-20-initial-deployment.json`, `AI_USAGE.md` |

Windows operational notes:

- Shell tools can start outside the requested working directory. Use an explicit
  `Set-Location C:\School\devops\individual_assignment\devops_assignment2` and
  `git -C <repo>` where useful. Do not operate in the A1 reference by habit.
- Sandbox account Git access may fail as “dubious ownership” or “not a repository”.
  Use the approved actual-owner execution context; do not add a global safe.directory
  exception or bypass a permission block. Stop/report genuine permission blocks.
- Azure CLI 2.93.0 is installed at
  `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd` if PATH is stale.
  Current CLI default is the student subscription. Owner handles expired login
  interactively; never automate passwords/MFA or ask for them in chat.
- `tools/azure_bootstrap.py` fixed Windows non-ASCII directory output handling;
  do not reintroduce the original strict UTF-8 reader crash.
- Local pinned Terraform 1.14.1 and actionlint are in ignored `.tools/`.
  Providers are AzureRM 4.46.0 / AzAPI 2.7.0 with committed lock checksums.
  Normal production Terraform runs through GitHub OIDC, not a local manual apply.
- New A2 `.venv` currently has the schema-validator dependencies, not the complete
  service/root test environment. Install the appropriate pinned dev manifest
  before local service tests. Do not modify the A1 environment as a shortcut.
- Node browser dependencies were installed under `tools/browser/`; the explicit
  live checker uses installed Chrome in an isolated headless session. Screenshots
  are ignored. It is operator-run and must not be added to CI against Azure.
- Check Docker Desktop before local Compose work. A successful CI SQL stack
  does not prove the current local daemon is running. Never delete user volumes
  or reset user databases just to make tests pass.
- Read/write UTF-8 explicitly. `apply_patch` can partially apply before reporting
  an error; inspect current files before retrying. Never stage `.env`, caches,
  state/plans/tfvars, generated credentials, DBs or uploads.

## Safe resumption checklist

Read rules/timeline → verify branch/status and current main/CD → inspect pending
handoff changes → name the next overarching runtime outcome within the active
request → implement/test/review in the A2 checkout → batch one factual AI row →
push/PR/CI/merge/CD → collect genuine live evidence → update these notes within
that milestone. Do not spend a commit merely acknowledging this handoff.

## Assignment 1 professor feedback (79/100) and A2 adjustments — added Nov 20

Source: `../assignment1_feedback.pdf`. Points were lost on: commit spread (51% of commits on the
last day, cap is 40%), AI_USAGE (disposition "Not recorded; author to confirm" in 54 of 66 rows,
vague explanations like "UI tweaks", one "TODO", and grouping per commit instead of per
interaction), a weak testing ADR (ADR-4), SMART goals without stakeholders, a brittle
date-dependent test, 194 files vs the 15-50 guidance (standalone UI prototype still shipped),
README setup scattered/Windows-only, and cross-domain imports/writes.

Adjustments for A2 (rubric: Process 25% = ADR 10% + AI_USAGE 10% + cadence/PR flow 5%):
1. **Cadence:** keep Nov 21 and Nov 22 to one milestone each; never let one day exceed 40%
   (at 13 total, max 5). Nov 20 already has 3. No last-night pile-up.
2. **AI_USAGE (largest recoverable loss):** before the next commit, fill every A2 row's
   Disposition (Accepted/Modified/Rejected) from the actual diffs/review history, and make
   "What changed and why" name real files/functions. Current A2 rows: 39 say "Not recorded",
   13 pending own-words. Infrastructure files (workflows, Dockerfiles, Terraform) must be
   logged and explained. Owner writes "In my own words" with real function names.
   OPEN OWNER DECISION: the grader noted "one row per commit rather than one per interaction".
   Option that keeps the owner's low-burden policy: keep one row per commit but list each
   distinct interaction inside it with its own disposition.
3. **ADR 9/10:** ADR-4 was marked weak for alternatives about *who* wrote tests and for not
   saying what was prioritized toward 70% or left thin. ADR 9 must name real alternative
   testing approaches, which core logic per service is covered thinnest, and the stub-vs-compose
   justification. ADR 10 needs a genuinely deferred capability with a concrete trigger.
   Entries 1-5 stay unchanged.
4. **Tests:** no date-dependent assertions. A2 tests use relative `timezone.now()+timedelta`
   and zone-aware conversion (checked: `test_account.py:66` uses ZoneInfo, no fixed offset).
   Keep new tests (migration, outage) clock/DST independent.
5. **Seam hygiene:** no cross-domain model imports or writes to another service's tables
   (A1 lost points for `save_group` importing `discovery.models.Event`). A2 split should make
   this structural; verify nothing in services/ reaches across.
6. **Repo size:** 407 tracked files; the root monolith (`discovery/`, `groups/`, `templates/`,
   `static/prototype`, demo posters) is still shipped as the CI regression reference. OPEN
   OWNER DECISION: remove or archive it before submission? Confirm CI no longer depends on it.
7. **README:** consolidate setup (compose, single service, tests, deploy, live URL) at the top,
   include Linux/macOS commands, a full env-var table with defaults, and move UI/feature
   description below. Report needs named stakeholders if any goals are stated; goals should be
   product outcomes, not restated course requirements.
8. **Commit messages:** specific (what and why); no "Initial commit"-style filler.

## Owner decisions applied Nov 20 (after the feedback review) — uncommitted, batch into the next milestone

1. **AI_USAGE format:** the 11 A2 rows now list each interaction numbered inside the Prompt cell with a matching numbered Disposition (Accepted / Modified / Rejected), and "What changed" names real files/functions. Still one row per commit; the owner's "In my own words" cells are untouched and still pending. When adding the next row(s), keep this format and fill dispositions factually. Historical A1 rows were left unchanged. Pre-edit backup of the file is not in the repo.
2. **Monolith archived, not deleted:** removed from the tree with `git rm` (staged, uncommitted): `accounts/ app.py config/ discovery/ groups/ notifications/ manage.py requirements.txt static/ templates/ test_schema.py test_web.py` and `tools/build_demo_posters.py build_pickle_rick_poster.py fetch_dj_photos.py` (407 -> 219 tracked files). Preserved at **local git tag `archive/a1-monolith` = 181474919a9451414fd6a6087e6d681c8a737c0a** and a local zip `../archive/a1-monolith-at-181474919.zip` (outside the repo). **The tag must be pushed (`git push origin archive/a1-monolith`) BEFORE the PR's CI runs**, because the new CI job `archived-monolith-split-import` checks the tag out into `legacy-monolith/` and runs `tools/check_split_import.py` with `MONOLITH_ROOT`. The old `monolith` job (manage.py test) was dropped; the split import check passed locally against the archived code, and the Groups/Discovery boundary check passed. `ui/` already carries its own copies of the assets, so nothing under `static/` was needed. README now has an "Archived Assignment 1 monolith" section; SCHEMA.md/ROUTES.md carry an archive banner. Large A1-era README sections still remain (full README rewrite is Nov 22 work). Never delete the tag; do not touch `devops_assignment1`.
