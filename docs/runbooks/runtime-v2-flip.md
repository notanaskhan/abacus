---
title: "Runtime v2 flip (M17): agent runs, real time and engagement runs, per pilot firm, Tue May 2, 2028"
owner: builder
alarms: [SLO-05, SLO-06, sse-delivery-p95]
last_rehearsed: never
rehearse_by: 2028-04-14
---
# Runtime v2 flip (M17)

| Field | Value |
|---|---|
| Owner | ayushkbhatia (the three flags' registry owner) operates; notanaskhan approves. Both founders' approvals are on every request (P-29, DEC-809) |
| Task | P-10-T54 (TASK-7424; DEC-4413); chapter 10 M17 |
| When | **Tue May 2, 2028**, in the 19:00 CT slot, after the 2028 window, one pilot firm at a time |
| Before it | the shadow of engagement runs on staging (at least 14 days, 50 runs) and the canary from **Mon Mar 20, 2028** |
| Rehearse | on staging before Fri Apr 14, 2028 with the synthetic firm PF-X1; set `last_rehearsed` then |
| Rollback | flags off, in reverse order; **runs persist** (see Rollback) |
| Related | RB-28 (real-time delivery), RB-65 (SSE edge), RB-23 (workflow engine), RB-01 (deploy), `firm-rollback.md` |

M17 moves a pilot firm's agent work onto runtime v2: runs with plans a person approves, questions,
proposals a person applies, live updates on the dock, and Run on an engagement. The agent never
approves, signs or decides (INV-1); these flags only show people the run and its proposals.

## 0. The flags, in order
One flag per request (DEC-809), three requests in one PR, numbered by file
(`deploy/production/ops-requests/flip-2028-05-02-<code>-1.yaml` to `-3.yaml`):

1. `agent_runtime.v2`: run commands, plan approval, questions, redirect, retry, stop, the loop
   harness and the capability routes. Off: 404, runs stay on the v1 path.
2. `realtime.sse`: `GET /v1/events` and the run streams. Off: 404 and every client polls (the kill
   switch, RB-28).
3. `engagement_run.enabled`: Run on an engagement (SHL-13). Off: 404 and the dock shows no Run.

All three registry entries expire **2027-05-07**; P-10-T56 renews them on the Tue Apr 25, 2028
train with an expiry after the window. Until then `runtime_v2_flip check` refuses the plan
(`flag_expires_before_slot`).

## 1. Preconditions (each recorded in the request)
1. **The window is closed** and the firm's Tuesday 19:00 CT slot is open (`make windows`).
2. **Journeys green on staging within 24 hours:** J11 (`j11-workbench`; b1 on the runtime, b2–b3
   `test.fixme` until W-02) and J23 (`j23-audit-partner-morning`; step 1 the engagement run), plus
   `e2e/agents/run-stream.spec.ts` (P-10-T50) and the API-level journey
   `test_runtime_v2_journey.py` (P-10-T49).
3. **Load report** of P-10-T51 met its targets (stream first event p95 under 500 ms, commit to
   delivery p95 at or under 2 s, database connections under 70%) or names dated fixes.
4. **Shadow evidence** (below) passes.
5. **Provider terms** cover each capability's route (ADR-114); a capability whose `client_data`
   is `none` stays off for the firm's real data whatever the flags (DEC-4411).

## 2. Shadow of engagement runs and the canary
- **Shadow on staging:** from at least 14 days before the request, PF-X1's engagements get an
  engagement run on each P-8 trigger point the live `EngagementAgent` acts on, with the flags on
  for PF-X1 only. Record runs started, runs completed, and any invariant failure
  (`abacus_tools.harness.invariants`: INV-1 to INV-5) in `shadow.json`:
  ```json
  {"shadow_from": "2028-03-01", "shadow_to": "2028-04-20", "runs": 64,
   "invariant_failures": 0, "canary_from": "2028-03-20"}
  ```
  Floors: 14 days, 50 runs, zero invariant failures. Build the file from the database rather
  than by hand:
  ```bash
  python -m abacus_tools.runtime_v2_flip shadow --firm <PF-X1 tenant> --from 2028-03-01 --to 2028-04-20 --canary-from 2028-03-20 --staging > shadow.json
  ```
  It counts the firm's `engagements.run` runs started in the window and runs INV-1 and INV-5 over
  its audit events; it refuses a firm that is not synthetic and exits 1 when a floor is missed.
- **Canary from Mon Mar 20, 2028:** the staging canary (SLO-10's 15-minute flow) adds one
  runtime v2 run on PF-X1: start, plan approval by the canary person, completion, and the dock's
  stream. `canary_from` is its first green.
- The shadow link in each request is the CI run that produced `shadow.json`.

## 3. Write and check the request
```bash
python -m abacus_tools.runtime_v2_flip render --firm <tenant> --code <PF-code> --shadow-run <link> --out deploy/production/ops-requests
```
```bash
python -m abacus_tools.runtime_v2_flip check deploy/production/ops-requests/flip-2028-05-02-<code>-*.yaml --shadow shadow.json
```
The check refuses anything but: three requests, one per flag, numbered in the order above, one
firm, the M17 slot, J11 and J23 named, the same shadow link, this runbook's rollback, operator
ayushkbhatia and approver notanaskhan, flags that expire after the slot, and the shadow floors.
`flip-precheck` then runs on the PR per file (journeys fresh, slot, pilot firm).

## 4. The flip (Tue May 2, 2028, 19:00 CT)
1. Merge the PR after notanaskhan's approval; `ops-task.yml` runs the flag CLI for `-1`, `-2`,
   `-3` in order (the flip guard runs again at execution).
2. After each flag, check for 5 minutes: API 5xx and `abacus-staging-api-unhealthy` analogues in
   production, `SseDeliveryLagMs` p95 (after `-2`), SLO-05 schedule-to-start.
3. After `-3`, start one engagement run on the firm's chosen engagement with the firm's champion:
   the plan shows, the champion approves it, items arrive on the dock live.

## Rollback
Flags off in reverse order: `engagement_run.enabled`, then `realtime.sse`, then
`agent_runtime.v2`, with `make flag FIRM=<tenant_id> FLAG=<name> VALUE=false OPERATOR=<name>
REASON=runtime-v2-flip` (or `--all-off` for every flag the firm has). Nothing is deleted:
**runs persist**: runs, plans, questions, proposals, run records and traces are insert-only and
stay readable; a run in flight keeps its workflow and can still be stopped by a person; an applied
proposal stays applied and is undone, if at all, by a person in its window. With
`agent_runtime.v2` off the firm's runs go back to the v1 path. Raise SEV2 if a rollback is needed
after the champion's first run.

## Rehearsal (staging, before Apr 14, 2028)
On PF-X1: render and check a request for PF-X1 with a dated slot, run the three flags on through
the flag CLI, run J11 and J23, then the rollback in reverse order, and confirm the runs started
during the rehearsal are still readable afterwards. Record the times and set `last_rehearsed`.
