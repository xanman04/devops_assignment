# Bassline

Bassline helps people discover music events and find attendance groups. Assignment 2 separates the existing Python/Django application into two JSON services and a static HTML/CSS/JavaScript UI.

Live application: **https://xcieu2023ui.z1.web.core.windows.net/**.

## Run locally

From a clean clone with Docker Desktop's Linux engine running:

```powershell
docker compose up --build
```

Open http://localhost:8080. Compose starts Discovery, Groups, SQL Server 2022, an idempotent database initializer and stock nginx serving the same static files used in Azure. Each service has a separate restricted database login. Preserve data volumes when redeploying. [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) documents local credentials, ports, tests/coverage and single-service operation.

## Boundaries and behavior

[Discovery](services/discovery/README.md) owns accounts, events, venues, genres, artists, follows and event reports. [Groups](services/groups/README.md) owns attendance groups, memberships, requests, messages and group notifications. Protected Groups actions validate identity/event eligibility through timed HTTP calls to Discovery; public group summaries and own-database health continue during Discovery failure.

The [static UI](ui/README.md) calls both configured API URLs. Tokens stay in memory. Group participation exercises UI to Groups to Discovery server-side calls. Venue/report moderation is independently authorized by the API; hiding a reported event uses a narrow permission. Accounts, event forms, follows, private-group approvals and chat are supported. Persistent user image uploads are deliberately deferred (ADR 10); bundled artwork is supported.

See [SERVICE_BOUNDARIES.md](SERVICE_BOUNDARIES.md), [DATA_MIGRATION.md](DATA_MIGRATION.md), each service's openapi.json, [system.yaml](system.yaml) and ADRs 6-10 in [ADR.md](ADR.md). system.yaml lists runtime configuration and read environment variables; secrets have no public defaults. Ordered migrations run under a database lock at startup and are never edited after application.

## Checks and deployment

CI lints/tests each service with at least 70% core coverage, validates contracts/schema/migration drift, builds images, and runs real SQL Server Compose, service-boundary, browser and infrastructure checks. CI never uses Azure SQL. Main CD requires CI at the same SHA, publishes full-SHA GHCR images, applies [Terraform](infra/README.md), uploads configured static UI files and checks both exact-version own-database health endpoints.

[AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md) documents reproducible setup and subsequent pipeline-only changes. The professor's November 20 student guide supersedes the shared-class instructions: own student group, two Consumption Container Apps, two free-offer SQL databases, Storage static hosting and scoped GitHub OIDC.

[RELEASE_VERIFICATION.md](RELEASE_VERIFICATION.md) covers explicit production participation/outage checks, recovery and the selected-account moderator grant. The first November 24 run passed participation/outages but failed fixture cleanup; restoration succeeded and the correction is batched with moderation. [Migration evidence](evidence/azure/) contains real retained rows/applied records; original November 23 startup console logs were not recovered. Local tests do not substitute for production proof.

## Handoff and submission

[CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md) records dated progress/open work; [COMMIT_TIMELINE.md](COMMIT_TIMELINE.md) records the ledger and remote evidence. [AGENTS.md](AGENTS.md) requires few cohesive milestone commits and one grouped [AI_USAGE.md](AI_USAGE.md) row per commit; the owner alone writes the own-words explanations. The owner reports the extended deadline as November 29, 2026 at 23:59 Europe/Paris. Final report, explanations and matching tagged/deployed full SHA remain submission work.

## Archived Assignment 1

The original monolith is preserved at tag archive/a1-monolith (181474919a9451414fd6a6087e6d681c8a737c0a); read that tag's README for its runtime. CI uses it only for split export/import regression. SCHEMA.md and ROUTES.md describe the historical monolith; current service models and OpenAPI documents describe Assignment 2. The separate local A1 checkout stays at recorded baseline 33bf6d10fa11cfb9a63586dcb4ab2fb33eb8d384; both checkouts share the same remote history.

## Copyright

Copyright © 2026 Xander Chen. All rights reserved.

This project is published for demonstration purposes only.
No rights to use, copy, modify, or redistribute the original project code are granted.

Third-party components and assets remain the property of their respective owners
and are subject to their own licenses and terms. In particular, Funnel Display
is licensed under the SIL Open Font License 1.1; see static/fonts/OFL.txt.
See DJ_SOURCES.md for third-party media credits and sources.
