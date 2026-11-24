# Production release verification

This is an **explicit operator exercise after successful main CD**, separate from
CI. It uses the real Azure databases and temporarily stops each own Container App,
one at a time. Do not add it to push/PR CI, run it during another production
operation, or claim a local stub proves the Azure result.

## Preconditions and execution

1. Confirm the current main deployment succeeded at the exact current main SHA.
   Confirm `deploy.yml` has **no running or pending run** before dispatching.
   GitHub's default concurrency permits one pending run; another dispatch can
   replace that pending run. Both production workflows share the same lock.
2. The existing Azure OIDC identity, scoped own group and application secrets are
   reused. Add `LIVE_CHECK_PASSWORD` as a generated random GitHub secret of at
   least 32 characters; never print it or commit it. It is not a public demo password.
   Retain it on reruns: existing managed fixture accounts are never password-reset.
3. Run from the canonical repository, on main only:

```powershell
gh workflow run verify-live.yml --repo xanman04/devops_assignment --ref main -f operation=verify
```

The workflow refuses stale main/images, other branch/repository contexts and
unexpected app names/hosts. It creates two reserved **non-staff, non-superuser**
fixture accounts and one clearly named approved verification venue/event through
the Discovery image. Existing unrelated names, privileged accounts or password
mismatches cause a refusal. Preparation is atomic, limited to these records and
uses the restricted Discovery database identity. It never resets/drop databases
or changes ordinary accounts. The controlled future event remains for reuse;
the run-created attendance group is deleted through the authorized Groups API.

The runner needs temporary SQL connectivity while preparing the fixture; its
own-IP rule is named `<prefix>-verify-<run-id>` and removed afterward. Passwords
travel as environment values passed by name to Docker, never command arguments,
repository files or evidence artifacts. No additional Azure compute or database
is provisioned.

## What it checks

- All pre-existing category IDs/names in the November 23 before-data snapshot
  remain, every slug is nonempty/unique, and both actual Django migration records
  `0014_genrecategory_slug` / `0015_genrecategory_slug_unique` have applied timestamps.
- Actual browser login, private group creation, join request, approval and chat
  through the UI → Groups → Discovery seam, at desktop/mobile sizes.
- With **Groups actually stopped**, Discovery health/browse still work and the
  affected Groups page presents a retryable error.
- After recovery, with **Discovery actually stopped**, Groups own health and
  public group records still work; a newly observed protected Groups request
  returns 503 and the UI explains the affected flow.
- Final service recovery and exact-version database health. Screenshots and
  sanitized JSON are uploaded as `live-release-evidence` on success or failure.

Stop/start uses the versioned [Azure lifecycle API](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/container-apps/stop?view=rest-resource-manager-containerapps-2025-07-01).
Recovery markers are saved **before** a stop request, including ambiguous remote
responses. Recovery waits for an in-flight stop to settle before starting the app.
The Node `finally` path and workflow `always()` step both attempt restoration.

## Recovery and evidence limits

A force-killed/lost runner can prevent cleanup. Dispatch the same main workflow
with `operation=recover` if that happens; this requires no old runner files:

```powershell
gh workflow run verify-live.yml --repo xanman04/devops_assignment --ref main -f operation=recover
```

Explicit recovery validates only the two own app names and expected SHA-tagged
images, starts stopped apps, checks their own-version health, and removes only
orphaned `<prefix>-verify-<digits>` SQL rules. It does not change replica limits,
replace databases, expand roles, or require the Git main head still to match an
older exercise. A failed recovery is a visible failed workflow: inspect it and
report any remaining stopped app or fixture group ID; never mark the exercise green.

The original November 23 migration console output was not found in the logging
workspace during the November 24 query (the seven-day table search was empty).
Applied database records plus retained rows are real evidence, **not reconstructed
startup console logs**. Preserve this distinction in the report. New evidence
does not erase the genuine failed/fixed SQL Server CI runs from November 23.

Tools/tests: `tools/live_release.py`, `tools/browser/check_participation_live.cjs`,
`prepare_live_check` in Discovery, fixture tests and `tools/test_live_release.py`.
CI runs only the local/fake recovery tests; no Azure credentials enter those jobs.
