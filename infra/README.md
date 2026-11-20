# Student Azure infrastructure

The professor's November 20 guide, `class_content/a2-azure-deployment-guide.pdf`,
supersedes the original shared-class Azure contract. Assignment 2 uses an active
personal Azure for Students subscription, `rg-<IE-prefix>`, a Storage static
website and a user-assigned GitHub OIDC identity. The IE-owned subscription named
`Azure Simple IE Instituto de Empresa, S.L.` is for the group project.

This Terraform root defines one Consumption environment, its metered Log
Analytics workspace, two apps with zero/one replicas, one SQL server and two
serverless free-offer databases. The UI Storage account, private state container,
resource group and managed identity are documented initial-setup dependencies.
No Static Web App, VM, paid image registry or shared-class credential is used.

Before provisioning, verify the selected subscription's enabled student offer
and its allowed-region policy. SQL can use a different allowed region if the
free offer is unavailable in the main region. Never silently fall back to paid
databases. The free offer controls the 60-minute pause and 32 GB storage limit;
the configuration deliberately omits both overrides. SQL's `useFreeLimit` and
`freeLimitExhaustionBehavior=AutoPause` use the versioned Azure API through
AzAPI because the pinned AzureRM SQL resource lacks those fields. Both fields
are defined by the [Microsoft SQL 2023-08-01 API](https://learn.microsoft.com/en-us/azure/templates/microsoft.sql/2023-08-01/servers/databases).
Confirm Local backup redundancy support in the chosen SQL region. A rejected
region must fail setup, never silently relax the free-offer or LRS settings.

Initial setup uses `bootstrap_mode=true` and the course placeholder image on
port 80 while restricted contained SQL users are created. Production deploys
use `bootstrap_mode=false`, published SHA-tagged images and port 8000. Database
URLs and Django keys are Container App secret references, never literal
environment values. Ingress CORS stays off; each service restricts CORS itself
to the Storage website origin. Startup probes allow five minutes for startup
and SQL resume. Health remains about the service's own database.

Terraform state contains secrets. Use the AzureRM backend in a PRIVATE blob
container in the UI Storage account, never `$web`, source control or a public
artifact. Blob leases lock state. Bootstrap grants the managed identity
Contributor only on this resource group. Configure the backend with `use_oidc=true` and
`use_azuread_auth=true`, and grant the identity Storage Blob Data Contributor
on the own UI/state Storage account during initial setup. Upload the UI using
`--auth-mode login`; do not rely on Storage account keys. Provider
auto-registration is disabled: initial setup
registers only the five providers in the course guide. Both Terraform providers
explicitly use OIDC and disable subscription-level provider registration.
New data-plane role assignments can take several minutes to propagate: retry
backend initialization/UI upload on an initial 403 instead of broadening roles.
The 0.1 GB/day Log Analytics cap stops ingestion for the rest of that day; if
logs appear missing, check the cap and retain the pipeline's startup/health
diagnostics. The cap bounds credit usage and does not prove an absence of errors.

Run `terraform init -backend=false`, `terraform validate`, and `terraform test`
for offline configuration checks. Tests mock both providers and assert the
resource counts, scale bounds, student offer, secret references and image tags.
They never connect to Azure. CI repeats them. A valid mock plan does not prove
subscription eligibility, regional capacity, OIDC/RBAC access, real provisioning
or deployment. Those need the owner's login and actual deployment evidence.

The course-required 0.0.0.0 SQL firewall exception admits Azure-hosted sources
across tenants; it is not a substitute for authentication. Use a strong generated
administrator password and separate restricted contained users. Remove temporary
operator/runner-IP firewall rules after setup, including when setup fails.

See [AZURE_DEPLOYMENT.md](../AZURE_DEPLOYMENT.md) for exact bootstrap/pipeline
commands, GitHub configuration and live evidence requirements.
