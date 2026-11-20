# Student Azure deployment

Use the professor's November 20 guide, not the older shared-class contract.
Local course source: `C:/School/devops/class_content/a2-azure-deployment-guide.pdf`.
The pipeline and initial-setup scripts are committed so their exact commands
can be reviewed and explained. Nothing below requires sending passwords in chat.

## Verify the account first

Azure CLI was installed with Microsoft's package:

```powershell
winget install --id Microsoft.AzureCLI --exact
az login --use-device-code
python tools/azure_preflight.py
python tools/azure_preflight.py --subscription <active-student-subscription-id>
```

Reopen the terminal after installation. If PATH has not refreshed, call
`C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd` explicitly.
The preflight is read-only: it lists subscriptions, reads the selected offer and
intersects allowed-region policies. It never selects an account or provisions.
An IE-owned subscription with an Enterprise Agreement offer is not proof of a
personal Azure for Students subscription. Activate/renew the student offer at
the professor's link, complete academic verification, then sign in again.
Do not substitute pay-as-you-go or the group project's subscription.

## One-time bootstrap

After confirming the student subscription and allowed regions:

```powershell
gh auth status
python tools/azure_bootstrap.py --subscription <student-id> --student xc.ieu2023 --repo xanman04/devops_assignment --region <allowed-region> --sql-region <allowed-free-sql-region>
```

This is a real mutating setup command. Do not run it with an Enterprise/class
subscription. A custom subscription name does not establish eligibility: the
script checks the offer and Enabled state before creating anything. SQL free
availability/LRS support still needs the actual initial deployment; if the
region rejects the offer, stop and choose another allowed SQL region. Do not
silently enable paid overflow or replace an existing populated database.

The script's exact Azure commands are in `tools/azure_bootstrap.py`. In order it:

1. Selects the confirmed student subscription and registers only Microsoft.App,
   Microsoft.OperationalInsights, Microsoft.Sql, Microsoft.Storage and
   Microsoft.ManagedIdentity, waiting for registration.
2. Creates `rg-xc-ieu2023` tagged with the owner, refusing to adopt an existing
   untagged/other-owner group. It creates `xcieu2023ui` as Standard_LRS StorageV2
   with TLS 1.2, public blob ACLs and shared-key access disabled. The static
   website remains public through its dedicated web endpoint.
   Reruns verify the account ownership, privacy flags and tier; an existing state
   container must also be private. Existing resources are not trusted merely
   because their names match.
3. Creates `xc-ieu2023-github`; grants Contributor on this group only and Storage
   Blob Data Contributor on this Storage account. The interactive owner gets
   the same data-plane role for setup. Grants the two professors specified by
   the guide Reader on the group; no invitations/messages are sent by the script.
4. Adds the exact named and numeric-ID repository OIDC subjects for main, with
   issuer `https://token.actions.githubusercontent.com` and audience
   `api://AzureADTokenExchange`. Existing differing trust is rejected.
5. Enables the Storage static website with `index.html` using Azure AD login;
   creates the PRIVATE `xc-ieu2023-tfstate` container, separate from public `$web`.
6. Sends IDs and generated application/DB credentials directly to GitHub secrets
   through stdin, never a repository file or printed command. Existing generated
   passwords are retained on rerun. Sets configuration variables, enabling Azure
   deployment only after all setup steps succeed.

RBAC propagation can take several minutes. If data-plane setup returns 403,
wait and rerun the same command; never expand the role to subscription scope.
If professor lookup/role assignment fails, resolve the directory access before
enabling deployment. Bootstrap creates no service principal/client secret and
does not yet create the domain apps/databases.

| GitHub secret | Purpose |
|---|---|
| AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID | Scoped managed-identity OIDC login |
| SQL_ADMIN_PASSWORD | Initial contained-user setup only |
| DISCOVERY_DB_PASSWORD, GROUPS_DB_PASSWORD | Separate domain identities |
| DISCOVERY_SECRET_KEY, GROUPS_SECRET_KEY | Independent Django secrets |

Variables are `PREFIX`, `RESOURCE_GROUP`, `UI_STORAGE`, `AZURE_REGION`,
`AZURE_SQL_REGION` and `AZURE_DEPLOYMENT_READY`. No credentials go in variables.

## Same-commit CI/CD

Pushes to feature branches and PRs run `ci.yml`. Main runs `deploy.yml`, which
first calls the SAME CI workflow through `workflow_call`; CI has no Azure
credentials. A failure in any CI job prevents image publication/deployment.

After successful CI, the publish job builds each domain Dockerfile and pushes
`ghcr.io/xanman04/bassline-<service>:<full-SHA>`, with `provenance: false` per the
course guide. Make each first-created package public in its GitHub package
settings before the first Azure deployment; the deploy preflight refuses to
contact Azure while either package is private. Never conceal a genuine failure
or deliberately create one for report evidence.

With setup enabled, the deploy job requests a GitHub OIDC token, signs in with
`azure/login`, and initializes Terraform's PRIVATE Azure AD blob backend with
lease locking. `tools/deploy_azure.py` then:

1. If apps do not yet exist or still use the course placeholder, applies the
   initial placeholder configuration, opens a temporary runner-IP SQL firewall
   rule and creates each contained user inside its own database. It checks own
   login success and other-domain login denial. The temporary rule is removed
   in `finally` on ordinary failed setup. A forcibly terminated runner can leave
   that rule: inspect/remove `<prefix>-initial-runner` before retrying if the job
   was cancelled or timed out. No SQL passwords appear in argv/files.
2. Plans the real runtime with the tested SHA. `deployment_guard.py` rejects
   deletion/replacement, other prefixes/groups, unapproved resource types,
   extra/duplicate apps or databases beyond their exact approved names,
   nonzero minimum replicas, extra replicas, paid SQL overflow and forbidden
   free-offer overrides before applying. Plans are private runner files, never
   uploaded or committed, and removed afterward. Never use force-unlock casually.
3. Applies the real images, generating `ui/config.js` from Terraform's service
   URLs. Publishes a clean UI folder to `$web` using Azure AD, excluding operator
   README/nginx/template files. It never uploads state or service source files.
4. Allows up to eight minutes for both own-database health endpoints to return
   HTTP 200 AND the exact tested SHA; a stale healthy revision does not count.
   The UI presents a clear starting-up/retry message for HTTP 503. The workflow
   summary records the full SHA and public URL.

Concurrency queues production runs instead of cancelling an in-flight apply.
After setup, all infrastructure and application changes go through main CI/CD.
When initial setup is not enabled, main publishes images and explicitly reports
deployment pending; a green publish-only run is NOT successful CD evidence.

## November 20 initial deployment evidence

The own Azure for Students subscription was verified Enabled and selected. Initial
setup completed in Germany West Central: own resource group, private Azure AD
state container, main-only OIDC subjects, scoped identity, professor Reader roles
and GitHub secrets. A Windows directory-name encoding error was corrected by
forcing UTF-8 in CLI subprocesses; a regression test covers this setting. The
idempotent rerun preserved existing resources and generated secrets.

The [first successful main CD run](https://github.com/xanman04/devops_assignment/actions/runs/44742390475)
deployed full SHA `7bd8ba217b4ac9216bee99860c6c076c958de595` to
https://xcieu2023ui.z1.web.core.windows.net/. Both services returned HTTP 200,
`db: ok` and that exact version. The run verified each contained login worked in
its own database and was denied access to the other domain database. The temporary
runner-IP rule was removed; only the prescribed Azure-services rule remained.
The earlier run was canceled before deployment during the local-checkout
clarification; cancellation is not a failed-and-fixed run for report purposes.

Azure's actual database configuration was checked: each uses Gen5 serverless
0.5–1 vCore, the free offer with exhaustion AutoPause, 60-minute auto-pause,
32 GiB offer-controlled size and Local backups. The environment's only workload
profile is Consumption; each app has a configured minimum of zero and maximum
of one replica. Storage/logging still meter usage; these settings do not promise
zero cost or prove a full pause/resume cycle.

An explicit production browser check renders the real UI, calls both APIs from
the browser origin, checks exact-version database health and captures desktop
and mobile screenshots. It creates no accounts/events and never runs in CI:

```powershell
npm ci --prefix tools/browser
$env:BROWSER_UI_URL = 'https://xcieu2023ui.z1.web.core.windows.net/'
$env:DEPLOYED_SHA = '<full deployed SHA from the successful run>'
node tools/browser/check_live.cjs
```

This uses an installed Chrome browser in an isolated headless session. Screenshots
are local ignored files under `tools/browser/artifacts/live/`. Initial screenshots
were visually inspected. The public seeded-row baseline is committed at
[`evidence/azure/2026-11-20-initial-deployment.json`](evidence/azure/2026-11-20-initial-deployment.json):
22 stable genre IDs/names and zero public events. This is an API projection,
not a database backup or proof of the future preserving migration.

## Verification boundaries and remaining evidence

Local tests use mock Terraform providers, fake plans/responses and disposable
local databases. They prove contract checks and error paths, not Azure regional
capacity, role propagation, image visibility, cold starts or live persistence.
Student activation, initial setup and the first live run are now verified above.
Live account/group writes, partial-failure behavior and a fully paused database
resume cycle have not yet been demonstrated on Azure.

Save a real successful main CD run link and any genuine failed-and-fixed run
with its cause. Capture populated Azure rows BEFORE a later in-place migration,
then the retained rows, startup migration log and deployment link afterward.
Never run CI tests against Azure SQL or recreate databases for evidence.
The owner supplied the official `system.schema.json` on November 20. The root
`system.yaml` describes both services, their environment, peer calls and Azure
names. Run `python -m pip install -r tools/requirements-validation.txt` then
`python tools/check_system.py`; the infrastructure CI job runs this gate too.
It validates the unmodified course schema, repository paths, environment reads
and peer API methods. Schema validity alone does not establish live reachability.
The later Azure migration, authenticated/partial-failure evidence, remaining UI
adapters, report and final submission tag still need completion. Do not present
prepared infrastructure or local tests as additional live evidence.
