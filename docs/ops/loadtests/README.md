# Load tests: the runbook (Q-03-T046)

How a load test is run, read and recorded, from creating the perf stack to destroying it. Targets
and scenarios are chapter 10 section 10.11 (`docs/plan/10-quality-strategy.md`); the harness is
`abacus_tools.loadtest` (Q-03-T035, T044); the profiles are `make seed-staging PROFILE=x1|x25|x100`
(`abacus_tools.synthetic.fleet`). The session procedure is the `loadtest` skill
(`.claude/skills/loadtest/SKILL.md`).

**Never against a database a hosted build is using.** Load runs on the ephemeral perf stack
(QD-6), which has its own database, or on a laptop's own stack. Never on staging's shared database,
never on production, never while a deploy, migration or seed holds that environment's deploy lock.
The harness refuses any non-loopback target and any environment but `local` or `test` (DEC-397);
the fleet loader refuses production, a non-synthetic firm and a staging deploy in flight.

**Results only.** A result file holds percentiles, counts, error codes, rates and the build SHA. It
never holds a request body, a token, a tenant's data, a hostname or an account ID: the repository is
public. Load runs on synthetic firms only, so there is no client data to leak, and the rule stays.

## 0. What exists today (2026-10-27)

| Piece | State |
|---|---|
| Harness: YAML profiles, client-side p50/p95/p99, SSE, Temporal load (`make loadtest PROFILE=`) | built (Q-03-T035) |
| Journey content: `journeys` (J02, J04-PBC, J12 with persona weights), `pbc_import_burst` (300-item import), `smoke` | built (Q-03-T044) |
| Firm profiles x1, x25, x100 (`make seed-staging PROFILE=`) | built (Q-03-T044); x25 rehearsed on a laptop's throwaway Postgres 2026-11-01 (below) |
| Tax-surge content in every profile: 5 to 15 returns per firm (four in five Feld-shaped 1040s with an organizer and the 8879 family's PDFs, one in five a Ridgeline-shaped 1065 with a four-recipient K-1 set), through the organizer and bridge services | built (Q-03-T132, DEC-1675); the x25 tax-surge run (Q-03-T131) waits for the perf stack and Q-03-T106 |
| Perf stack `infra/envs/perf` and its create and destroy workflow | **not built** (Q-03-T036) |
| Chapter 10 scenarios: `monday_9am`, `deadline_surge`, `pbc_import_fairness`, `sse_soak`, `backfill_business_hours`, `failure_under_load`; the post-deploy `x1_smoke` | built (Q-03-T043) |
| `--dry-run` (`make loadtest DRY_RUN=1`): the plan, no request | built (Q-03-T043) |
| The x1 smoke's p95 trend, its ticket and its quality-report row (`abacus_tools.loadtest.trend`) | built (Q-03-T043) |
| A harness target inside the perf stack's VPC, the fleet loader on its ops task, and the post-deploy job that runs the x1 smoke and the trend | **not built** (Q-03-T036; the deploy workflow step is the builder's) |

So the perf-stack sections (2, 3, 4 and 6) are the procedure Q-03-T036 must make true.
Each step there names what it waits on. Section 1 can be walked today, on a laptop.

## 1. Rehearse on your own stack (laptop, x1)

Use this to check a profile before a window, and as the x1 baseline.

1. Check no hosted build is running against anything you will touch: `gh run list --workflow deploy-staging.yml --status in_progress` prints nothing. (A laptop stack shares no database with a hosted build, but the check is the habit.)
2. Start the stack: `make dev` (in its own terminal), then `make migrate`.
3. Seed Brightwater Hale with the portal people: `make seed-demo SLICE=portal`. For x1's fleet firm as well: `cd backend && uv run python -m abacus_tools.synthetic.fleet --profile x1` (loopback only; a second run writes nothing).
4. Prove the harness: `make loadtest PROFILE=smoke`. It runs 5 seconds and prints a table.
5. Run the journey mix: `make loadtest PROFILE=journeys` (5 minutes, 20 users). `make` passes Northwind's ids from `abacus_tools.loadtest.journey_vars`; add more with `VARS="name=value"`.
6. Optionally the import burst: `make loadtest PROFILE=pbc_import_burst` (2 minutes). The first run adds 300 requests to Northwind's 401(k) audit; later runs count them as duplicates.
7. Read the result (section 4). Exit code 0 is a pass, 1 a failed pass rule, 2 a refusal or a misconfiguration (the message says which).

A laptop's numbers are not the gate's numbers: they prove the scenario plays and give a trend.

Before any run, anywhere: `make loadtest PROFILE=<name> DRY_RUN=1` prints the plan (personas and
their shares, each group's steps with the ids filled, targets, streams, Temporal operations) and
sends nothing. Use it to check a profile and its ids before a window.

## 2. Create the perf stack (needs Q-03-T036)

The perf stack is `infra/envs/perf`: production instance sizes, in the staging account, its own
database, created for a window of about 48 hours and destroyed after. Its cost per window is
recorded in the vault, never here.

1. Book the window in the sprint plan, and request provider quota increases a month before any x100 test (ADR-075, Q-03-T160).
2. Check no staging deploy is in flight (`gh run list --workflow deploy-staging.yml --status in_progress`) and none is planned for the window.
3. Dispatch the perf create workflow Q-03-T036 adds, with the release image SHA under test. Record the SHA: every result names it.
4. Wait for the workflow's checks: migrations at head on the perf database, the API and worker healthy, the fakes for SES, Bedrock, QuickBooks and DocuSign configured (chapter 10 section 10.11.4).

## 3. Seed a profile (needs Q-03-T036's ops route)

1. Seed through the perf stack's ops task, never from a laptop: the command is `make seed-staging PROFILE=x1` (or `x25`, `x100`), which runs `abacus_tools.synthetic.fleet --staging --profile x1`. It refuses unless the environment is staging-type, no staging deploy is in flight, and every fleet firm id it touches is synthetic. **x25 and x100 also refuse any database host that does not start `abacus-perf`** (`fleet.perf_guard`): Q-03-T036 must name the perf stack's database instance that way, and staging's shared database never matches. x1 may seed staging (one firm). Every check reads as the firm under row-level security, so it holds as the owner role.
2. The x1 profile is 1 firm; x25 is 25 and x100 is 100 Brightwater-size firms: 46 seats, 184 clients, 27 audits with a 16-request PBC list each, two client people per audit, the rollout and portal flags on. Firm n is the same firm in every profile, so x25 after x1 adds 24.
3. Re-running a profile writes nothing (`N write(s), M already loaded` in the output). That is the check that the seed is complete.
4. Laptop rehearsal of x25 (TASK-2471, 2026-11-01; `fleet.load(dsn, "x25")` on a throwaway local Postgres, never a hosted one): 25 synthetic firms, 2,500 memberships (46 seats and 54 client people each), 4,600 clients, 675 audits, 675 PBC lists, 10,800 requests and 4,600 `client.created` audit rows through `organisations.api.create_client`; 9,025 writes in 76 s; the re-run wrote nothing in 8 s. The profile's content is complete; only its run on the perf stack waits for Q-03-T036.

## 4. Run and read

1. Run the profile from the perf stack's runner (Q-03-T036): the same `abacus_tools.loadtest.run --profile <name>`, with the perf API as its target.
2. The report is printed and written to `backend/.local/loadtest/<profile>-<UTC stamp>.json` and `.md` (git-ignored). Each endpoint group has: kind (http, sse, temporal), count, errors and their codes, p50, p95, p99 and max in milliseconds, rate per second, and its p95 target.
3. **Pass rule** (chapter 10 section 10.11.1): every group with a target holds its p95; the error rate across all samples stays under 0.1%; and no SLO alarm fires in the window. A failed rule names the group and the number (`j04_pbc_requests: p95 612 ms over 500 ms`).
4. **Server side, same window:** open the OpenTelemetry traces and the CloudWatch metrics for the API and worker on the perf stack (`docs/ops/slos.md`, the observability skill), filtered to the run's start and end. Check: p95 server time per route against the client p95 (a large gap is the network or the client, not the app); database connections and slow statements; the outbox relay lag; Temporal schedule-to-start for the `interactive` and `batch` classes; worker memory over an SSE soak. Note what you saw in words and numbers; never paste a trace with data.
5. **Fairness** (`pbc_import_fairness`): with load firm 1 seeded beside Brightwater Hale, Hannah Leclerc's 300-item import must not push the `other_firm_*` groups' p95 past 500 ms. Locally: `fleet --profile x1` first (section 1 step 3).

### The chapter 10 scenarios (section 10.11.3)

| Profile | Shape | What a human does during it | Must show |
|---|---|---|---|
| `monday_9am` | 46 users arrive over 10 minutes, then an hour of Home, Waiting on you, lists with counts and record reads | nothing | list p95 500 ms, record p95 300 ms |
| `deadline_surge` | portal sign-in starts and branding at the peak, staff working requests | nothing; uploads, 8879 sends and K-1 releases are not in it yet (the profile header says why) | portal and request targets under the burst |
| `signing_surge` | an hour of 8879 sends (E18), envelope reads and clients opening their Sign area (N-02-T47) | distinct drafts per send (Q-03-T131): after E18 goes once, sends answer 409 through the same checks | send and portal envelope view p95 500 ms; the provider queue drains in the hour, backing off on a 429 at its Retry-After |
| `pbc_import_fairness` | one firm's 300-item import, another firm reading | seed load firm 1 first | the other firm's p95 at target |
| `sse_soak` | 60 clients for 2 hours on the polling fallback (no stream route until P-15) | when P-15 ships: add the stream entry and run a deploy mid-soak | memory flat in OTel; polling within 5 s |
| `backfill_business_hours` | the Monday mix plus Temporal visibility reads | start the throttled backfill on the batch class through its ops command, at minute 5 | interactive targets unaffected |
| `failure_under_load` | the Monday mix for 30 minutes | kill one API task at minute 10, fail the database over at minute 20; note both times | recovery within SLO; no outbox event lost (count the outbox before and after) |
| `x1_smoke` | 5 minutes of the everyday read mix | nothing | the trend below |

### The x1 smoke after each staging batch deploy

1. After the batch deploy completes (never while one is in flight), run `x1_smoke` from the perf stack's runner and keep its JSON report with the earlier ones (the post-deploy job Q-03-T036 adds keeps them as workflow artifacts; never in git).
2. Run `python -m abacus_tools.loadtest.trend --history <reports> --out loadtest-trend.json --ticket ticket.md`. Exit 1 means a group's p95 rose more than 20% over its 4-week median: open a ticket with `ticket.md` as its body (results only). Exit 0 is no regression; a group with fewer than two earlier runs reads "no median yet".
3. Put `loadtest-trend.json` among the weekly quality report's inputs (`quality-report.yml`); the Ops table shows the row "x1 load smoke: p95 per group against its 4-week median".
4. Acceptance (Q-03-T043): this has run after two consecutive staging batch deploys and the trend is in the quality report.

## 5. Record the result

1. Write `docs/ops/loadtests/<yyyy-mm>.md` (Q-03-T052 writes `2027-03.md` for M7) with: the window, the build SHA, the profile and scale, the scenario files' git SHA, a copy of each report's Markdown table, the verdict, the server-side notes from section 4, and every failure with its ticket.
2. Results only: no hostnames, account IDs, tokens, tenant ids, request bodies or amounts. The fleet firms are placeholders ("Load Firm 007"); name them by number if at all.
3. A failure becomes a reliability-only batch (the ADR-093 error-budget rule) and a re-test before the gate. Link the tickets from the result file.
4. Feed the quality report: the gate's row links the result file.

## 6. Destroy the stack (needs Q-03-T036)

1. Within the window (about 48 hours from creation), dispatch the perf destroy workflow. It removes the database and its snapshots with the rest: nothing from a perf run is kept but the result file.
2. Check the destroy completed: the workflow's final step lists no perf resources left. Record the window's cost in the vault and the create and destroy dates in the result file.

## 7. When something goes wrong

| What you see | Do |
|---|---|
| `loadtest refused: ... is not a loopback address` or `environment ... is not local` | The harness is pointed somewhere it must never load. Stop. On a laptop, check `ABACUS_ENVIRONMENT=local` and the base URL. On the perf stack, the runner of Q-03-T036 is the only way in. |
| `refused: a staging deploy is in flight` | Wait for the deploy to finish; never cancel it to make room. |
| `loadtest refused: deploy lock held: ...` or `ABACUS_..._URL points at a hosted database` | The harness applies `db_guard` before every run (Q-03-T114): a deploy holds the lock of `ABACUS_DEPLOY_LOCK_ENV`, or a database setting names a hosted host. Wait for the deploy to finish (`make deploy-lock ENV=staging`); never point a local run at a hosted database. A dry run still works. |
| `refused: ... exists and is not synthetic` | A fleet id is held by a real firm. Stop and treat it as an incident (RB-08): a fleet id must never collide. |
| `needs --var <name>=...` | The profile reads an id `make loadtest` did not pass. Add `VARS="name=value"`. |
| The error rate is all `401` | The persona has no user on that stack: seed it (section 1 step 3) or check the subject in the profile. |
| SLO alarms fire on staging during a perf run | The perf stack is sharing something it must not. Stop the run, destroy the stack, open an incident. |
