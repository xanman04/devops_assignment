## November 27 remaining UI parity and submission documentation

Milestone 18: organiser listening-link editing (`/api/events/{event_id}/references/`) and the
profile collection (`/api/account/collection/`), closing the last non-deferred UI parity items,
with the README setup/variable tables, the ADR 9 testing update and corrected stale notes.
No migration. The November 24 moderator grant (run 45387120564) was refused because no `admin`
account exists, so it is still open. Remaining: owner AI explanations and AI disclosure,
register `admin` and run the grant if wanted, final report check, baseline/LMS audit and the
`submission` tag on the final deployed SHA by November 29 23:59 Europe/Paris.

## November 26 nearby artists

Milestone 17: the Near me panel lists the artists playing at the events shown, closing the
nearby-artist parity item. Failure emails reviewed: all refer to the fixed November 23 SQL
Server CI runs (45177569676, 45177595901) and the November 24 release exercises
(45382213269, 45387120564; rerun 45387312865 passed). Still pending: owner
listening-reference editing, profile collection/badges, final report placeholders, owner
AI explanations and the submission tag by November 29 23:59.

## November 25 UI parity milestone

Milestone 16 (working number): group ban management (`GET /api/groups/{group_id}/bans/`, "Remove and ban" and "Lift ban" in the group page) and richer Near-me filters (`tag`, `from`, `to` on `/api/browse/`, subgenre and 7/30-day selectors). One grouped AI row; owner explanation pending. Still pending UI parity: owner listening-reference editing, profile collection/badges and nearby artists; image upload is deferred by ADR 10. Remaining: report and evidence selection, owner explanations, baseline/LMS audit, submission tag by Nov 29 23:59.

# Assignment 2 commit timeline and remaining work blocks

## November 24 moderation release

PR 11 preserved b5d6b23eea1f93ca7313b95f5f8358f8a08d106d; main 5844b7e881a388cc73799fdbe435212e79da1823 passed [CD 45381034872](https://github.com/xanman04/devops_assignment/actions/runs/45381034872). That is substantive A2 commit 14 on the eighth date. The second milestone restores permission-gated moderation and corrects real live-check cleanup; on merge, total 15 with daily counts 1,2,1,2,2,3,2,2 (largest 20%). No daily quota or bookkeeping commit is needed.

The owner selected existing username `admin` for venue review, report review and reported-event hiding only. The post-CD moderator operation refuses a missing/inactive account and preserves passwords, staff and superuser flags. Migration 0016 introduces the narrow hide_reported_event permission; general event editing is not granted. One grouped AI row covers the whole milestone; only the owner writes its explanation.

[First live exercise 45382213269](https://github.com/xanman04/devops_assignment/actions/runs/45382213269) verified participation and both actual service outages, then failed moderator-only group deletion during cleanup. Separate restoration succeeded. Corrected cleanup uses guest-then-owner membership leave, including stale managed fixture groups; a successful rerun after deployment is still needed. Actual retained rows and applied migration timestamps are in evidence/azure/2026-11-24-after-slug-migration.json; original November 23 startup console logs remain unavailable.

Remaining: corrected live verification and explicit admin grant after CD, final report/evidence selection, owner AI explanations, baseline/LMS audit and matching full-SHA submission tag. No final tag exists. Deadline November 29 at 23:59 Europe/Paris is owner-reported. The historical November 20 snapshots and November 21-22 blocks below are superseded by this section.


Ledger initially verified November 20; active update November 24 below. All planning times below are **Europe/Paris**.
Read this with [AGENTS.md](AGENTS.md) and [CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md).
The owner requires minimal, substantial commits and one grouped AI-log row per
coherent commit. This schedule is a work plan, never permission to pad history.

## November 24 active work and extended deadline

The owner reports a one-week extension: **November 29, 2026 at 23:59 Europe/Paris**.
This supersedes the November 22 deadline and the dated November 21–22 work blocks.
Latest verified main at start of today's work: `17adff951ff284dc2d238c4c58025922051ad6ac`,
[successful CD 45179414430](https://github.com/xanman04/devops_assignment/actions/runs/45179414430).
There are **13 non-merge A2 code commits across seven dates**, including the necessary
November 23 SQL Server correction. The six-date/minimum-count conditions are covered;
do not create more commits to satisfy an obsolete daily quota.

Today's two substantial outcomes are (1) repeatable production migration/participation/
partial-failure verification with recovery and (2) restoring venue/report moderation to
the static UI. Keep all related code, tests, review corrections and factual AI fields
inside those outcomes. The working total after both is 15, not a number to pad toward.
The map fix, slug migration, ADR 10 and monolith archive were merged November 23;
older notes saying these are pending are historical. `RELEASE_VERIFICATION.md` describes
the new explicit production exercise; it is not a push/PR CI test and must run only
when CD has no running/pending run. Its live result is pending until actually executed.

## Requirements and November 20 position

- Extended deadline: **November 29, 2026 at 23:59** (owner report November 24); confirm any different official course timezone.
- Minimum **12 new meaningful commits**, across **six different calendar days**,
  with no day containing more than **40%** of the final Assignment 2 commits.
- Count real implementation milestones, not automatic PR merge commits.
  Push each completed milestone on its actual workday; local dates alone are
  insufficient. Never backdate, force-push, split trivial edits or create empty commits.
- Current total: **11 substantive commits**, pushed and merged, across
  **November 15, 16, 17, 18, 19 and 20**. The six-day spread is already covered.
- Current daily distribution: **1, 2, 1, 2, 2, 3**. Largest share is 3/11 = 27.3%.
  At totals of 12 or 13, three on November 20 remains below 40%.
- Recorded pre-A2 baseline: `33bf6d10fa11cfb9a63586dcb4ab2fb33eb8d384`.
  It is the recorded last A1 repository baseline; matching it to the actual LMS
  submission is still a final audit item, not something inferred from Git alone.
- ADR 6 was committed November 16; ADR 7 November 18; ADRs 8–9 November 20.
  The three-date ADR spread is already covered. **ADR 10 remains unwritten**;
  do not create entry 11 or manufacture another decision date.

## Completed milestones and observed remote evidence

Times are Paris local time. Git commit times and GitHub evidence are deliberately
separate. A push-triggered Actions creation time shows GitHub received that push
by then; it is not claimed to be the exact server push timestamp. For commits
batched in one PR, the merge proves the commit was remote by the merge time.

| Date | Commit | Cohesive outcome | Observed GitHub evidence |
|---|---|---|---|
| Nov 15 | `bfec4a3` | Public event API foundation | [PR 1](https://github.com/xanman04/devops_assignment/pull/1) created 23:18:49, merged 23:31:14; CI workflow was not yet present |
| Nov 16 | `6d2cf7e` | Ownership/contracts and ADR 6 | Included in [PR 2](https://github.com/xanman04/devops_assignment/pull/2), merged 15:25:17 |
| Nov 16 | `9416f8d` | Independently runnable Discovery | [Push CI](https://github.com/xanman04/devops_assignment/actions/runs/43885229864) created 15:23:35; PR 2 merged 15:25:17 |
| Nov 17 | `8aecfeb` | Groups extraction and HTTP seam | [Push CI](https://github.com/xanman04/devops_assignment/actions/runs/44089277255) created 14:05:31; [PR 3](https://github.com/xanman04/devops_assignment/pull/3) merged 14:06:51 |
| Nov 18 | `b973f87` | SQL Server, data movement and ADR 7 | Included in [PR 4](https://github.com/xanman04/devops_assignment/pull/4), merged 13:16:03 |
| Nov 18 | `923c10f` | Docker/Compose and real SQL checks | [Push CI](https://github.com/xanman04/devops_assignment/actions/runs/44301648397) created 13:12:04; PR 4 merged 13:16:03 |
| Nov 19 | `8eb5cee` | Static public Discovery UI | [Push CI](https://github.com/xanman04/devops_assignment/actions/runs/44546249823) created 15:40:09; [PR 5](https://github.com/xanman04/devops_assignment/pull/5) merged 15:45:01 |
| Nov 19 | `06f0429` | Static accounts and group participation | [Push CI](https://github.com/xanman04/devops_assignment/actions/runs/44550025767) created 16:01:01; [PR 6](https://github.com/xanman04/devops_assignment/pull/6) merged 16:04:41 |
| Nov 20 | `43772f5` | Terraform student Azure runtime | [Push CI](https://github.com/xanman04/devops_assignment/actions/runs/44720330796) created 11:34:07; [PR 7](https://github.com/xanman04/devops_assignment/pull/7) merged 11:40:35 |
| Nov 20 | `623b164` | Same-SHA CI/CD and secure bootstrap | [Push CI](https://github.com/xanman04/devops_assignment/actions/runs/44723732828) created 11:58:47; [PR 8](https://github.com/xanman04/devops_assignment/pull/8) merged 12:02:06 |
| Nov 20 | `c96f8d8` | Actual Azure launch, official schema and live verification | [Push CI](https://github.com/xanman04/devops_assignment/actions/runs/44744678768) created 14:28:57; [PR 9](https://github.com/xanman04/devops_assignment/pull/9) merged 14:35:36 |

November 20 deployed main: `181474919a9451414fd6a6087e6d681c8a737c0a`.
[Main CD succeeded](https://github.com/xanman04/devops_assignment/actions/runs/44745670962).
This is a working deployment, **not the final submission tag/SHA yet**.

## Historical remaining blocks — November 20 plan, superseded by extension

These blocks are the current forward plan, not a claim that each hour was
reserved earlier. No unattended work is scheduled. An agent must be actively
running an authorized task to implement, commit, push or merge.

**Working target: two remaining substantial milestones, yielding 13 total.**
The reason is the dependency between deploying the populated-table migration
and collecting its real evidence for the final report. Twelve remains preferable
if the remaining work can genuinely be finished as one coherent reviewed outcome.
Do not create a thirteenth commit just to satisfy this table. More than 13 is
acceptable only for genuine independently reviewable work or necessary recovery;
do not turn fixes, review rounds, documentation or author replies into microcommits.

| Paris date/time | Work block | Planned outcome / commit boundary |
|---|---|---|
| Nov 20, remainder | Read handoff, inspect source/brief, owner explanations and planning | No further commit merely for these handoff files or the map patch. Keep them with the next real milestone. |
| Nov 21, 09:00–12:00 | Audit remaining A1 UI conversion against source; prioritize required parity; inspect actual populated Azure data before choosing a useful additive migration | Scope the next cohesive runtime-completion milestone. Do not treat a pre-existing local backfill applied during Azure's first boot as the required later Azure migration. |
| Nov 21, 12:00–17:00 | Complete the remaining required runtime/UI conversion, including the verified map fix; implement and locally test the chosen preserving migration and related recovery/configuration/docs; draft ADR 10 from a real deferred capability | Keep related edits, tests and corrections uncommitted until the runtime outcome is reviewable. Do not add new product scope. |
| Nov 21, target 17:00–20:00 | Review staged diff; commit/push the substantive runtime milestone (working number 12); PR CI, merge preserving the commit, main CD | Capture before-data **before** deploying the new migration. Capture actual startup migration logs and after-data from this deployment. Target merge/deployment well before midnight, not a last-minute push. |
| Nov 21 evening | Demonstrate authenticated UI → Groups → Discovery flow and controlled partial failure; capture screenshots, run links and recovery evidence; owner explains grouped work | These checks depend on the deployed code. Record actual outcomes; batch any necessary corrections with the next coherent remaining milestone. Do not manufacture an outage failure run for CI evidence. |
| Nov 22, 09:00–13:00 | Resolve remaining real blockers, check brief/schema/OpenAPI/ADRs, produce the 4–5 page report with actual Azure evidence | Report must distinguish verified behavior, remaining limits and genuine failures. Owner supplies own-words AI entries and their own explanation/prose. |
| Nov 22, target 13:00–18:00 | Complete submission materials and final corrections as one coherent milestone (working number 13); feature push, PR CI, merge, same-SHA CD | Include these handoff/docs updates and any related pending evidence. No separate commits for hashes, AI-log rows, screenshots or a minor review fix. |
| Nov 22, 18:00–21:00 | Verify final deployed main SHA, real URLs, data retention, evidence/report consistency, AI disclosure and all process counts | Reserve this buffer for actual CI/CD or migration problems. Freeze optional scope. Never bypass a failed gate to meet a planning target. |
| Nov 22, target by 21:00; hard deadline 23:59 | Check existing tags; tag the exact verified deployed SHA `submission`, push tag, submit matching full SHA/repo/live URL and report | Aim to finish hours early. Use 23:55 only as an emergency latest operational target, leaving minutes before the official deadline; it is not the planned completion time. Keep the app reachable until grades are published. |

Runtime-completion scope is substantial and may exceed one day. Start early,
surface scope risk before evening, and prioritize assignment requirements over
cosmetic expansion. The clock does not turn unfinished work into a valid commit.

## Commit and disclosure rules at every boundary

1. State the proposed overarching outcome in one sentence. If it only says
   “update docs”, “fix a small bug”, “answer a prompt” or “record a hash”, batch it.
2. Review all staged changes and appropriate tests; preserve unrelated changes.
3. Add **one** factual AI_USAGE row for the coherent commit, grouping related
   prompts, tools and agents. The owner writes its own-words field; never invent it.
4. Verify checkout, feature branch, remote and upstream; push on the actual date.
5. Verify the intended PR head's CI, merge without squashing/rebasing the milestone,
   and verify main CD for the exact resulting main SHA.
6. Update this ledger with evidence as part of the same or next real milestone.
   **Do not commit ledger/hash/log bookkeeping separately.**

There are currently 11 grouped A2 AI-usage rows with owner explanations pending.
Surface them in small workstream teaching sessions now; do not let another large
last-night backlog form. A final full SHA can be entered in the submission form
or final exported report after the last commit; do not create a self-referential
“add my own commit hash” commit.

## Recheck, do not assume

Run Git/`gh` from the Assignment 2 checkout, inspect `git status`, and compare
`git log --no-merges 33bf6d10fa11cfb9a63586dcb4ab2fb33eb8d384..HEAD` with merged
PRs and push-triggered runs. Convert timestamps to Europe/Paris. Recount after
real changes. Six dates and the 40% cap are requirements, not reasons to create
more commits once the spread is satisfied.

## Update — Nov 23 (deadline moved; Nov 21 block done late, with real dates)

The Nov 21 and Nov 22 days passed with no commits; the professor moved the deadline.
Work resumed Nov 23 with real dates (nothing backdated). Milestone 12, "Preserve populated
genre data with a slug migration, archive the monolith, fix the map and record ADR 10",
adds migrations `discovery` 0014/0015, the map fix, ADR 10 and the archived monolith
(tag `archive/a1-monolith`). Counts after merge: 12 substantive commits on seven dates
(Nov 15-20 and Nov 23; Nov 20 = 3 of 12 = 25%, under the 40% cap). ADRs 6-10 span
Nov 16, 18, 20 and 23. Still open: Azure after-migration evidence (collect from the merged
main deployment), authenticated UI -> Groups -> Discovery flow and partial failure on
Azure, the 4-5 page report and README consolidation (commit 13), the `submission` tag.

## November 23 remote milestones and November 24 plan

| Date | Commit | Actual outcome / evidence |
|---|---|---|
| Nov 23 | `91d0bed` | Genre slug migration, monolith archive, map fix and ADR 10; first SQL Server CI failed genuinely: [45177595901](https://github.com/xanman04/devops_assignment/actions/runs/45177595901) |
| Nov 23 | `6a88845` | Necessary SQL Server migration correction; [PR 10](https://github.com/xanman04/devops_assignment/pull/10) merged; main CD [45179414430](https://github.com/xanman04/devops_assignment/actions/runs/45179414430) passed |

The earlier Nov 23 note's count of 12 omitted the subsequently required repair commit;
current verified Git count is 13. Daily distribution is 1/2/1/2/2/3/2 on Nov 15–20 and23.
There were no Nov21/22 commits; nothing is backdated.

| Date | Substantial work block | Commit boundary |
|---|---|---|
| Nov 24 | Reproducible main-only Azure release exercise, reserved nonprivileged fixture, migration retention/applied-record audit, authenticated browser flow, actual service stops and recovery | One release-verification milestone, working number14; related tests/docs/review fixes grouped |
| Nov 24 | Permission-gated venue/report moderation APIs and matching static UI, OpenAPI and authorization/browser checks; record actual release-exercise evidence | One moderation milestone, working number15; merge only passing exact-head CI, then verify same-SHA CD |
| Nov25–27 | Remaining required legacy UI parity/persistent media, evidence gaps, report preparation and owner explanations | Batch genuine remaining outcomes; no automatic commit per day or prompt |
| Nov28 | Submission audit, report evidence consistency, actual costs and remaining owner explanations | Reserve a recovery buffer; do not fabricate failed runs or author understanding |
| Nov29, target by21:00 | Verify final main/CD/data, check tag conflicts, push exact `submission` tag and submit full matching SHA/repo/live URL/report | Hard deadline23:59 Paris; keep app live through grades; no self-hash/bookkeeping commit |
