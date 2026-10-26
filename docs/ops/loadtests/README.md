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
| Firm profiles x1, x25, x100 (`make seed-staging PROFILE=`) | built (Q-03-T044) |
| Perf stack `infra/envs/perf` and its create and destroy workflow | **not built** (Q-03-T036) |
| A harness target inside the perf stack's VPC, and the fleet loader on its ops task | **not built** (Q-03-T036, T043) |
| Chapter 10's remaining scenarios, the post-deploy x1 smoke and its trend ticket | **not built** (Q-03-T043) |

So the perf-stack sections (2, 3 and 7) are the procedure Q-03-T036 and T043 must make true.
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

## 2. Create the perf stack (needs Q-03-T036)

The perf stack is `infra/envs/perf`: production instance sizes, in the staging account, its own
database, created for a window of about 48 hours and destroyed after. Its cost per window is
recorded in the vault, never here.

1. Book the window in the sprint plan, and request provider quota increases a month before any x100 test (ADR-075, Q-03-T160).
2. Check no staging deploy is in flight (`gh run list --workflow deploy-staging.yml --status in_progress`) and none is planned for the window.
3. Dispatch the perf create workflow Q-03-T036 adds, with the release image SHA under test. Record the SHA: every result names it.
4. Wait for the workflow's checks: migrations at head on the perf database, the API and worker healthy, the fakes for SES, Bedrock, QuickBooks and DocuSign configured (chapter 10 section 10.11.4).

## 3. Seed a profile (needs Q-03-T036's ops route)

1. Seed through the perf stack's ops task, never from a laptop: the command is `make seed-staging PROFILE=x1` (or `x25`, `x100`), which runs `abacus_tools.synthetic.fleet --staging --profile x1`. It refuses unless the environment is a staging-type environment on its own database, no staging deploy is in flight, and every fleet firm id it touches is synthetic.
2. The x1 profile is 1 firm; x25 is 25 and x100 is 100 Brightwater-size firms: 46 seats, 184 clients, 27 audits with a 16-request PBC list each, two client people per audit, the rollout and portal flags on. Firm n is the same firm in every profile, so x25 after x1 adds 24.
3. Re-running a profile writes nothing (`N write(s), M already loaded` in the output). That is the check that the seed is complete.

## 4. Run and read

1. Run the profile from the perf stack's runner (Q-03-T036, T043): the same `abacus_tools.loadtest.run --profile <name>`, with the perf API as its target.
2. The report is printed and written to `backend/.local/loadtest/<profile>-<UTC stamp>.json` and `.md` (git-ignored). Each endpoint group has: kind (http, sse, temporal), count, errors and their codes, p50, p95, p99 and max in milliseconds, rate per second, and its p95 target.
3. **Pass rule** (chapter 10 section 10.11.1): every group with a target holds its p95; the error rate across all samples stays under 0.1%; and no SLO alarm fires in the window. A failed rule names the group and the number (`j04_pbc_requests: p95 612 ms over 500 ms`).
4. **Server side, same window:** open the OpenTelemetry traces and the CloudWatch metrics for the API and worker on the perf stack (`docs/ops/slos.md`, the observability skill), filtered to the run's start and end. Check: p95 server time per route against the client p95 (a large gap is the network or the client, not the app); database connections and slow statements; the outbox relay lag; Temporal schedule-to-start for the `interactive` and `batch` classes; worker memory over an SSE soak. Note what you saw in words and numbers; never paste a trace with data.
5. **Fairness** (the PBC import burst, Q-03-T043): with more than one firm loaded, one firm's import must not push another firm's interactive p95 past target.

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
| `refused: ... exists and is not synthetic` | A fleet id is held by a real firm. Stop and treat it as an incident (RB-08): a fleet id must never collide. |
| `needs --var <name>=...` | The profile reads an id `make loadtest` did not pass. Add `VARS="name=value"`. |
| The error rate is all `401` | The persona has no user on that stack: seed it (section 1 step 3) or check the subject in the profile. |
| SLO alarms fire on staging during a perf run | The perf stack is sharing something it must not. Stop the run, destroy the stack, open an incident. |
