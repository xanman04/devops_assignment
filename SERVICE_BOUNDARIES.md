# Assignment 2 service boundaries

This is the extraction design, not a claim that both services are deployed.

## Ownership

| Owner | Records and behavior |
|---|---|
| Discovery | Accounts/passwords, sessions, profiles, Django permissions; genres, tags, venues, performers, events, listening references, reports, follows, event changes, event cards; event-change notifications |
| Groups | Attendance groups, memberships, join requests, bans, messages, history, notices; group-request and membership notifications |

Discovery keeps account IDs stable when importing existing data. Groups stores
plain account and event IDs, without foreign keys into Discovery's database.
Each service owns its own notification table. The static UI combines their
inboxes and sends read actions to the service that owns the notification.
Built-in Django auth group/permission tables belong to Discovery; they are not
attendance groups.

## Identity contract

Discovery authenticates passwords and issues short-lived bearer credentials.
Groups resolves the credential through Discovery over HTTPS with a bounded
timeout before protected actions, obtaining account ID, display name, active
state, and explicitly allowed Groups permissions. Raw caller-supplied user IDs
never authenticate a request. Tokens must not be logged or persisted in the
static UI's localStorage. The UI holds them in memory, requiring sign-in after
a full reload. Chat remains ordinary polling: every protected request and every
message write revalidates identity; no long-lived connection bypasses checks.
Deactivation/revocation must take effect on the next protected request. Account
deletion is not exposed; Groups retains historical account IDs and display-name
snapshots, with no cascade from Discovery. Token lifetime and revocation must
be implemented and tested before exposing authenticated APIs publicly.

Remote identity validation deliberately makes protected Groups actions depend
on Discovery availability. Groups returns a clear retryable 503 if validation
is unavailable; it must not grant stale privileges. This is simpler than
introducing signed-token key rotation in the first split. Public group reads
can continue using Groups-owned records while Discovery is unavailable.
Invalid/expired credentials return 401, inactive accounts return 403, and only
transport errors, malformed identity responses or peer 5xx return 503. The UI
must not retry 401/403 as availability failures.

## Event contract and partial failure

The first server-side cross-domain flow is creating/joining an attendance
group: Groups requests GET /api/events/{event_id}/ from Discovery, using
DISCOVERY_URL and DISCOVERY_TIMEOUT_S (proposed default 2 seconds). Missing or
nonpublic events return 404, cancelled events remain readable with cancelled
true and cannot accept new group participation. Calls happen before the local
membership transaction. A timeout, connection failure, or invalid response
returns a clear 503 with no membership change. No unbounded retries occur
inside the request. Discovery 404 becomes 404, cancellation becomes 409,
and Discovery 5xx/timeout/malformed data becomes 503. Local unique
membership constraints and idempotent repeated joins must prevent duplicate
membership when clients retry. The event could change immediately after validation;
cross-service atomicity is deliberately unavailable. Existing groups remain
as historical records if an event later becomes unavailable.
Group creation requires a caller-provided idempotency key scoped to account,
stored with its request payload fingerprint and resulting group in the same
Groups transaction. A repeated key/payload returns the original result; a
different payload with that key returns 409. Do not automatically retry any
unkeyed write after an ambiguous response.

Every service's health checks only its own database, never its peer. Groups
chat/listing failure behavior and identity failures must be tested separately.
Event-change notifications remain for explicit event followers, as in Assignment
1. Group membership alone does not subscribe someone to event updates. Groups
must not attempt to join Discovery's event-change tables for its inbox.

## Extraction sequence

1. Extract Discovery's models and business rules into services/discovery with
   independent settings, dependencies, migrations, JSON routes and tests.
2. Extract Groups against the contracts above; no cross-database access.
3. Move to SQL Server, import existing records with stable IDs, and exercise
   migration and seed behavior. SQLite during initial extraction is explicitly
   transitional and cannot be the submitted database backend.
4. Replace monolith pages with ui/ static pages and retire the root runtime.

The root application stays runnable during migration. Temporary source copies
must be reconciled and the old runtime retired before submission. The complete
OpenAPI documents and professor-provided system.schema.json remain required;
this design does not substitute for either.

## November 17 implementation status

Both service folders now have independent runtimes and databases. Groups stores
credential-free Person references for foreign account IDs, plain event IDs and
event title/start snapshots. HTTP identity grants are request-scoped, and event
participation facts are validated before entering local transactions. The UI,
SQL Server conversion, data import and deployment remain separate milestones.
The CI boundary check runs both actual processes against disposable databases.

For deployment, the owner reports that the professor credits infrastructure
managed explicitly with tools such as Terraform. Prefer Terraform definitions
of the assignment's required resources, applied by the deployment pipeline.
The lecture's compute comparison (Backend Components — SDD Session.pdf pages
19 and 22) presents general options and does not amend the explicit exclusion
of VMs. The professor-reported credit is an owner report, not a verified change
to the rubric. Continue to use Container Apps Consumption, serverless SQL and
Static Web Apps unless an updated assignment contract says otherwise.
