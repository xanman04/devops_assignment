# Bassline Assignment 2 — instructions for every agent

## Authority, scope, and handoff
- These rules apply to Claude, Codex, and all delegated agents. They supersede Assignment 1 automatic-commit and AI-disclosure instructions for Assignment 2.
- The owner is handing the bulk of implementation to Claude Max. Read this file before working. On November 15 the owner authorized the first implementation milestone and one coherent commit/push before midnight Europe/Paris. Continue only within the active request; Claude has not yet implemented changes.
- Assignment source: ../devops_assignment2/Assignment_2.pdf in the local workspace. On a fresh clone, obtain the actual brief and inherited Assignment 1 rules before implementation if unavailable. This checklist summarizes Assignment 2; it does not waive course requirements.
- Continue the same Bassline use case and GitHub repository, currently https://github.com/xanman04/devops_assignment1.git. The local Git root is C:/School/devops/individual_assignment/devops_assignment1. The adjacent devops_assignment2 folder currently holds the brief; do not start a separate submission repository there.
- Existing seam in ADR 2 is Discovery / Attendance Groups. Identity, notifications, cross-domain references, and failure behavior need explicit design. Earlier chat suggestions are proposals, not approved architecture.
- Prioritize accuracy and low token usage. Explain decisions so the owner can answer the written comprehension check. Report tested, untested, failed, and uncommitted work. Stop and report permission blocks.
- At the end of a turn that changes files, makes a decision, or leaves work open, add a short paragraph starting "State:" with at most two sentences.

## Automatic commits — strict owner preference
- Automatic commits are authorized once implementation is authorized, but only for completed, substantial, cohesive milestones. LESS IS MORE. Aim for the required 12 meaningful new commits. More are acceptable only for substantial independently reviewable outcomes.
- Assignment 1 produced roughly 170 commits and an unacceptable last-night burden of author explanations. Never repeat that workflow.
- Name a commit's overarching outcome in one sentence before making it. Batch related implementation, fixes, tests, review corrections, and documentation together. Keep intermediate work in the working tree until that outcome is ready.
- A prompt, small edit, tool call, changed file, agent turn, review comment, or minor bug fix is not an automatic commit trigger. Do not create separate commits for tiny changes, log updates, hash bookkeeping, or count-padding.
- Review the full staged diff and relevant checks before committing. Stage only intended files. Preserve unrelated user changes. Do not commit databases, uploads, virtual environments, caches, scratch artifacts, .env files, credentials, or signing material.
- During authorized work, ordinary commits and pushes to the verified feature-branch upstream are authorized without repeated permission questions. Verify repository, branch, remote, and staged content first. If a push fails, retain the local commit and report it.
- Automatic commits do not imply permission to implement from a planning-only request. They are an active-session workflow, not a timer or unattended scheduled task.

## Commit distribution, GitHub, and submission
- At least 12 NEW commits after the Assignment 1 submission, across at least SIX distinct calendar days. No single day may contain more than 40% of the Assignment 2 commits. They must be pushed; the professor checks push timestamps.
- Identify the actual Assignment 1 submitted baseline before counting. Track qualifying commits and dates, plus observed push evidence. Local commit dates alone do not establish when work reached GitHub.
- Use real work on real dates. Push completed milestones on their actual workdays. Do not accumulate everything locally for one final push, backdate, create empty commits, split trivial edits, manufacture failures, or rewrite history to manufacture compliance.
- Deadline is November 22, 2026 at 23:59. Use Europe/Paris for planning, and confirm any different official course timezone. November 17 is the mathematical last starting date for six days through November 22 inclusive, requiring work and pushes every day. Starting earlier gives flexibility.
- Twelve commits evenly spread as two on each of six days satisfy the numbers, but this is an illustration, never permission to split a coherent milestone. At a final total of 12, four commits on one day fit the cap; five do not.
- Evaluate distribution against the planned final total. Early in the project one day's share may temporarily exceed 40%; do not pad the denominator to fix it. Before committing, review counts and remaining genuine milestones and flag a cadence risk early.
- ADR entries 6–10 must themselves span at least THREE distinct commit dates. Plan authentic decision work on those dates.
- Changes reach main through pull requests from branches so CI runs before CD. Push feature branches, open PRs for coherent milestones, verify CI on the intended commit, and merge through PRs within the owner's authorized scope. Never push implementation directly to main.
- Preserve milestone commits in main's history. Avoid squash merging or rebasing that collapses the required commits or changes date evidence. Ordinary merge commits may add overhead; do not depend on them to satisfy the minimum.
- Never force-push, rewrite published history, or overwrite an existing submission tag without explicit owner direction.
- Every push and PR runs CI. Only push to main triggers CD, gated on successful CI for that SAME commit.
- Before final submission, verify the full graded SHA is on main, deployed successfully, and pushed before the deadline. Tag that exact SHA submission and push the tag. Check any existing tag first and resolve a conflict with the owner.
- Submit the repository URL and matching FULL SHA. Include the live UI URL in README and report. Missing/mismatched tag falls back to the last main commit before the deadline. Later commits are ignored. Keep the app reachable until grades are published.

## AI_USAGE.md — avoid an author-explanation backlog
- Owner clarification on November 15: keep ONE row PER COHERENT COMMIT, combining all related prompts, tools and agent contributions. Minimize the number of commits and author explanations. Never create one row per prompt or split commits to manufacture log entries.
- Keep the existing required columns: Date/commit, Tool, Prompt, Disposition (Accepted/Modified/Rejected), What changed & why, In my own words. Summarize related requests and link related commits when useful.
- Agents maintain factual fields as work proceeds. Include substantive infrastructure contributions, Dockerfiles, workflows, and IaC. Record accepted, modified, and rejected suggestions honestly.
- The owner writes the own-words field. Leave it pending until the owner supplies it; never invent their explanation or claim they already understood something.
- Surface a small grouped set of explanations while each workstream is fresh. Do not let dozens of pending fields accumulate until submission. Make infrastructure behavior and actual file/function names understandable.
- Preserve historical Assignment 1 entries. Do not restructure history without instruction.
- Assignment 1 explicitly says one row per meaningful interaction. The owner reviewed this on November 15 and directed that meaningful work be consolidated into a small number of coherent commits, each with one log row. Disclose this interpretation without claiming professor approval. This resolves the prior pending workflow question.

## Architecture and local runtime — brief §§1–3
- Same language/stack as Assignment 1; no language rewrite and no new product features required.
- Exactly TWO domain services, each its own process/container, Dockerfile, folder services/<name>/, and pinned dependency manifest. Soft cap about 12 third-party packages per service.
- Every table belongs to exactly one service. Cross-domain foreign keys become plain IDs with explicit integrity policy. Obtain other-domain data through HTTP, never another service's database. Move idempotent seed data with its owning tables.
- Static HTML/CSS/JS UI in ui/, fetching JSON from BOTH services. Convert server-rendered pages; services retain APIs only. Deploy UI on one Azure Static Web App. Configure API URLs, never hardcode them. Restrict each API's CORS to the UI origin.
- At least one USER-VISIBLE flow must call one service that calls the other server-side. Browser-only aggregation does not satisfy this requirement. Configure peer URLs via environment variables. Every outbound call has a timeout.
- Stop either service and verify the other continues its own domain. Design the affected flow's clear error/degradation/cache/retry behavior.
- Local docker-compose.yml at repository root starts a clean clone with docker compose up --build. Two domain containers, one SQL Server 2022 container (mcr.microsoft.com/mssql/server:2022-latest), and one database/login per domain.
- db/init.sql creates local databases/logins idempotently via a one-off compose service. Each login can access only its database. Each service reads DATABASE_URL.
- Local UI uses the SAME static files mounted into a stock server image, e.g. nginx:alpine, with no UI Dockerfile. This and the required database/init containers are permitted supporting containers; no third domain service/gateway.
- Dockerfiles must avoid COPY . ., secrets and .env inclusion, pin dependencies, and run as non-root.
- Each GET /health returns JSON with own DB read/write status and version (git SHA), 200 when healthy and 503 otherwise. Peer availability must not determine own health.
- Log at least method, path, status, and duration per request to stdout.

## Data and migrations — brief §4
- Replace SQLite with SQL Server, checking ORM/driver compatibility and porting raw SQL.
- Commit ordered versioned migrations, automatically applied at startup, tracked in the database, exactly once. Second boot applies none. Never edit an applied migration.
- Include at least one change to an ALREADY POPULATED table that preserves rows. Table recreation does not qualify. Document recovery for a bad migration in ADR 7; forward-only is allowed.
- Never drop tables on boot, recreate databases on deploy, or delete volumes to redeploy.
- Plan two Azure deployment stages early: deploy and capture populated data, then deploy the data-preserving migration. Save before/after data, migration startup log, and deployment-run link for the report.

## CI/CD and secrets — brief §5
- GitHub Actions in .github/workflows/. On EVERY push and PR, install, lint, test EACH service, enforce at least 70% core-logic coverage PER service, validate system.yaml against the provided schema and each OpenAPI document against OpenAPI, and build every image. Any failure fails CI.
- Unit tests per service plus at least one cross-domain integration test against compose or a justified stub (ADR 9). CI uses a local SQL Server container and NEVER Azure SQL.
- On main only, after same-commit CI success, publish images tagged with commit SHA, deploy those images, deploy the static UI with service URL configuration, and fail CD unless both deployed /health endpoints return 200 within a bounded cold-start-aware wait.
- Use GHCR by default. Justify any Azure Container Registry fixed cost.
- Professor-provided service principal credentials and UI deployment token are GitHub secrets. Service DB passwords and other secrets are GitHub secrets passed as Container Apps secrets, referenced by configuration, not literal plaintext environment values.
- No secrets anywhere in repository or Git history. A pushed secret is compromised. Within 24 hours rotate/revoke owner-created credentials and replace the GitHub secret; for professor-provided credentials notify the professor for rotation. Remove current exposure and record incident details in README. Do not send a notification as the user without authorization.
- Unresolved leaked credentials cap the final grade at 40/100. Do not conceal an incident through deletion or history rewriting.

## Azure contract — brief §7
- Azure only. Existing class resource group rg-sdd-3a or rg-sdd-3b; confirm class. Never create a resource group or touch another student's resources.
- Confirm IE username. Prefix EVERY created resource with its email local-part, dots replaced by hyphens. Shared service principal is scoped to the class group and cannot assign roles.
- Maximum two Container Apps, two serverless SQL databases, and one Static Web App, even temporarily. One environment. UI name <prefix>-ui, logical SQL server <prefix>-sql, database names <prefix>-<service>-db.
- Container Apps Consumption, min replicas 0 and max 1 for each. Public HTTPS ingress for browser access. Configure via environment variables and secrets through pipeline/IaC.
- Both DBs on one logical SQL server. General Purpose Gen5 serverless, min 0.5/max 1 vCore, shortest allowed auto-pause delay, max 2 GB, locally redundant backups. Separate restricted login per service. Allow Azure services in firewall, own IP only while needed.
- Handle database resume errors (40613), connection retry/backoff, container cold starts, and startup migrations before requests within HTTP timeout. Account for this in deployment health checks and ADR 8.
- Deploy only through pipeline after documented initial setup (README steps or IaC). No subsequent manual portal changes. Use class credentials only on own prefixed resources.
- No always-on compute, VMs, App Service plans, dedicated Container Apps profiles, lingering Container Instances, AKS/Kubernetes, brokers, background job runners, other DB products, service meshes, or third domain/gateway service. Document a worthwhile deferred option in ADR 10.
- Use required pay-per-use products; justify any other fixed-cost resource in ADR 8. Verify actual costs rather than promising idle is literally free. Keep live until grades published and remove unnecessary experimental resources.

## Documentation and evidence — brief §§6,8–9
- Keep ADR 1–5 text, marking changed decisions Status: Superseded by [N]. Add EXACTLY five new entries, 6–10, same format, spanning three commit dates.
- ADR 6 covers split, cross-domain calls, whether ADR 2 held, and reasons for moving seam.
- ADR 7 covers data movement/ownership, lost integrity and compensation, migrations and recovery.
- ADR 8 covers Azure resources/costs, scale-to-zero/cold starts, paused DB retries, startup migration concurrency, and 100x traffic.
- ADR 9 covers CI gates, cross-domain tests/stubs, and deliberate test gaps.
- ADR 10 covers one deliberately deferred capability and when it becomes worthwhile. Justify infrastructure/migration/failure-handling choices in relevant entries.
- Commit OpenAPI 3 documents per service with EVERY endpoint including health, methods, parameters, request/response schemas and status codes. Calls must match the peer's documented shapes.
- Obtain the professor's actual system.schema.json; do not invent a replacement. Commit it and root system.yaml starting with "# yaml-language-server: $schema=./system.schema.json".
- system.yaml must match code/deployment and list student/prefix/public URL, UI path/resource/calls, Azure group/environment/SQL server/registry, service paths/ports/health/migrations/resources, every read environment variable/default, and cross-domain endpoints/timeout/failure policy. Secrets have secret: true and no default.
- README covers clean-clone compose, single-service operation, tests/coverage, deployment and reproducible initial setup, and live URL. Update other existing architecture docs when changes make them inaccurate.
- Deliver a 4–5 page report with before/after architecture, deployment flow/resource names, DB diagram per service, Azure migration evidence, user-visible partial-failure evidence, successful main CD link, and a genuine failed-and-fixed run link with cause. Include syllabus AI disclosure.
- Final deliverables are repository URL, full tagged/deployed SHA, live URL, required source/config/docs/report, and attendance at the written comprehension check in the first class session after deadline.
- Grading weights: split/system 20%, containers/migrations 15%, CI/CD 20%, tests/observability 10%, docs/report 10%, process 25%. Written comprehension score multiplies the subtotal. Explain the system and infrastructure throughout, rather than deferring understanding to the end.

## November 17 infrastructure guidance from the owner
- The owner reports that the professor credits explicitly managed backend infrastructure and infrastructure as code. Prefer a Terraform definition of the required Azure resources for the deployment milestone, with resources/settings the owner can explain, applied through the pipeline.
- The class source is C:/School/devops/class_content/Backend Components — SDD Session.pdf. Its compute comparison (pages 19 and 22) discusses VMs, containers and managed options in general; it does not itself change the assignment contract or establish an extra-credit promise.
- Assignment 2 still explicitly requires Container Apps Consumption, serverless Azure SQL and Static Web Apps, and excludes VMs/always-on compute. Do not provision VMs or substitute another deployment platform based on the lecture discussion. Ask for an explicit updated assignment instruction if the professor changes these constraints.
- In this context, manually managing infrastructure means writing/reviewing its configuration and understanding the backend components, with automated reproducible deployment. Preserve the requirement that changes after initial setup run through the pipeline rather than manual portal edits.
