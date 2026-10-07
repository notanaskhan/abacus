---
id: TASK-018
title: Work-class queues and admission control
spec: SPEC-003
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16]
risk_zone: amber
status: awaiting-plan-approval
branch: task-018-work-classes
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-003. All asynchronous work runs on four work-class task queues with their own worker pools, behind one `dispatch`, with per-firm and per-engagement caps (ADR-071). Every model call is admitted through the gateway against shared provider capacity, by priority, degrading visibly (ADR-072).

## Scope
All of SPEC-003 (AC-1 to AC-16), once approved. Excluded: the budget hierarchy and metering (ADR-069), the second model route (ADR-073), autoscaling, and Terraform (TASK-014).

SPEC-003 approved by the founder on 2026-10-07 (all recommendations, Q1–Q7). Delivered as three PRs (D1).

## Context to load
- Spec: `docs/specs/SPEC-003-work-classes.md`
- ADRs: ADR-071, ADR-072, ADR-017, ADR-069, ADR-090, ADR-093, ADR-094, ADR-047
- Code:
  - `backend/src/abacus/kernel/temporal.py`
  - `backend/src/abacus/worker/__main__.py`
  - `backend/src/abacus/modules/connections/retrievals.py` and `workflows.py`
  - `backend/src/abacus/modules/agents/screenings.py`, `spec.py` and `workflows.py`
  - `backend/src/abacus/ai_gateway/__init__.py`
- Reference: `docs/architecture/reference/` (unit of work, backend module); the `temporal-workflow` skill

## Plan
- [ ] Plan approved by human

### Design (for founder review)

**§1 Delivery: three PRs, each with its own independent tests and reviews (D1).**
| PR | Delivers | ACs |
|---|---|---|
| 018a Queues | `WorkClass`, `dispatch`, four worker pools plus the legacy queue, DISPATCH-001, classes on workflows and agent specs, the metrics foundation, the ADR-069 naming amendment | AC-1–5, AC-15 (schedule-to-start), AC-16 |
| 018b Caps | Firm and engagement slots, fair hand-out, `queued` status with reason and estimate, `capacity_timeout` | AC-6–8, AC-13, AC-14, AC-15 (slots) |
| 018c Admission | Provider buckets, `gateway.admit`, priority and degradation, 429 handling | AC-9–12, AC-15 (admission) |

**§2 Kernel: `abacus.kernel.dispatch` (018a).**
- `WorkClass = Literal["interactive", "time_sensitive", "background", "batch"]`. `queue_for(cls)` returns `f"{settings().temporal_task_queue}-{cls.replace('_', '-')}"`.
- Registration:
  - each module's `WORKFLOWS` becomes `dict[type, WorkClass]`, the "registry" option in spec §7;
  - the worker and `dispatch` read it from the module `api`s;
  - a workflow that is registered without a class, or with an unknown one, raises at import (AC-4).
- The call: `dispatch(workflow_name, input, *, id, id_reuse_policy, id_conflict_policy, execution_timeout=None)`. It looks up the class by name, starts the workflow on `queue_for(cls)`, and logs `dispatch.started`. The caller's trace continues (TASK-013).
  - The two call sites (`connections/retrievals.py`, `agents/screenings.py`) switch to it, keeping their ID policies.
  - Because `kernel` never imports modules, the class map is registered into the kernel at import, the same inversion pattern as walls.
- **Activities run on the workflow's queue,** which is Temporal's default, so no per-activity `task_queue`.
- **DISPATCH-001** (`banned_patterns`): `start_workflow`, `execute_workflow`, `signal_with_start` or a `task_queue=` keyword anywhere outside `kernel/dispatch.py` and `worker/__main__.py` fails the build (AC-3).
- **Agent specs** gain `work_class` (required; the screener is `time_sensitive`), `essential: bool` (Q2; the screener is `true`) and `cheaper_tiers: list[Tier]` (default `[]`). The spec loader and codegen reject a spec without a class (AC-4).
- **ADR-069 amendment (Q2):** a new short ADR, "ADR-105: ADR-069's flag is `essential`". Accepted ADRs can't be edited, so this records the rename.

**§3 Worker (018a).**
- `python -m abacus.worker [--classes a,b]` (default: all four) builds one Temporal `Worker` per class: same workflows and activities, its own queue, its own `max_concurrent_activities` and `max_concurrent_workflow_tasks` (new settings, by class).
- For one release it also builds a worker on the legacy queue `settings().temporal_task_queue` (AC-16). The setting `serve_legacy_queue` defaults to true, and a follow-up removes it.
- They run together under the existing SIGTERM and relay handling; one failing stops all.
- `make dev` and CI are unchanged (one process serves all four, Q7).

**§4 Caps and fair hand-out (018b).**
- **Wait in the workflow, not in an activity (D2).** Slots are taken by a short activity `slots.acquire`, which returns granted, or `waiting` with an estimate. When waiting, the workflow marks the run `queued` (an activity), sleeps on a durable timer (backoff from 1 s to 30 s, with jitter from `workflow.random()`), and asks again. Waiting holds no worker slot and survives deploys and crashes.
  - The slot is held for the whole run, released by `slots.release` in the workflow's `finally`.
  - Each activity renews the lease (`lease_until = now() + 15 min`, database time). An expired lease is reclaimed by the next `acquire` (§12).
  - The workflow changes are behind `workflow.patched("work-slots")`, and new histories are recorded (`retrieval-v2-*`, `screening-v2-*`). The v1 histories still replay.
- **Cross-firm fairness needs a view across tenants, which forced RLS forbids (D3; changes spec §7).** The slot ledger (`work_slots`: holders, and `work_waiters`: who waits since when) is a platform table with no app privileges, like `users`. The app reaches it only through `SECURITY DEFINER` functions owned by `abacus_owner`, with a fixed `search_path`: `work_slot_acquire(holder, engagement_id, class)` and `work_slot_release(holder)`. The function takes the tenant from `current_setting('app.tenant_id')`, never from an argument, so a caller can only act for its own firm. It returns only its own decision and estimate, never other firms' identities or counts (spec §13).
  - Rows hold identifiers and counts only.
  - `schema_check` lists both tables in `NON_TENANT_TABLES` and `GLOBAL_TABLES` (protected; needs approval).
- **Rule inside `acquire`:** one transaction, with an advisory lock per class.
  1. Reclaim expired leases.
  2. Upsert the waiter.
  3. The waiter is *eligible* if its firm is under the firm cap and its engagement is under the engagement cap for the class.
  4. Grant only if the class is under its class capacity (setting `class_capacity`; default: the class pool's `max_concurrent_activities`) and this waiter comes first among eligible waiters, ordered by (its firm's last grant in this class, oldest first; then waiting since, oldest first). That is round-robin across firms and oldest first within a firm (Q3, AC-8).
- **Estimate:** `estimated_start_at` = now + (eligible waiters ahead ÷ grants per minute in the class over the last 10 minutes). Null when there were no grants recently (§12).
- **Caps** (Q4), settings by class: `firm_cap` (interactive 20, time-sensitive 20, background 10, batch 5) and `engagement_cap` (half). A cap of 0 pauses (§12).
- **Maximum wait** (Q6): the workflow tracks time queued. Past the class maximum, it fails the run with `capacity_timeout`, through the existing audited `fail_run`.

**§5 Status changes (018b).**
- `retrieval_runs` and `agent_runs` gain `queued` (with `queued_reason` and `estimated_start_at`).
  - A run is created `running` as today (the API's "already started" check treats `queued` as active too).
  - It moves `running ↔ queued` while waiting, and ends as today.
- The forward-only triggers, the `finished` CHECKs and the active-run unique index are widened to treat `queued` like `running`.
- Migration 0013, additive; `capacity_timeout` joins both workflows' failure codes.
- The retrieval and screening GETs expose `queued_reason` and `estimated_start_at`; the client is regenerated.

**§6 Gateway admission (018c).**
- **Bucket:** `provider_capacity(provider, model, rpm, tpm, requests_left, tokens_left, refilled_at, blocked_until)` is another platform table. It is reached only through `SECURITY DEFINER` functions `capacity_admit(provider, model, threshold_pct, tokens)` and `capacity_block(provider, model, seconds)`.
  - **Admit:** refill by elapsed database time, then decrement atomically only if both buckets stay above `threshold_pct`. It returns admitted, or waiting with a retry-after.
  - Limits are 80% of the provider's (settings) (Q5).
- **Priority by reserves (D4):** each class may only take capacity while the remaining share is above its threshold: interactive 0%, time-sensitive 0%, background 25%, batch 50% (Q5). A deferrable agent uses the next class's threshold (interactive → time-sensitive → background → batch), so within a class essential goes first (AC-10). This needs no cross-process queue, and it can never exceed the limits (AC-9).
- **`admit`:** `ai_gateway.admit(attribution, work_class, essential, estimate)`.
  1. It tries a cheaper tier when the spec lists one and the threshold failed (none today; AC-11).
  2. If still not admitted, it raises `NotAdmitted(reason, retry_after)`.
  3. `screening.screen` turns that into a non-retryable `ApplicationError("NotAdmitted")`.
  4. The workflow marks the run `queued` (reason `provider_capacity`, or `deferred` for batch and background), sleeps for `retry_after` with jitter, and calls the activity again. This is the same loop as §4: no busy loop, and no worker slot held.
- **429 handling (AC-12):** `ProviderError` gains `rate_limited: bool` and `retry_after`. On a 429 the gateway calls `capacity_block` and raises `NotAdmitted`, never retrying itself.
- **Fail closed:** if the capacity store is unreachable, the result is `NotAdmitted("provider_capacity")`.
- **Span:** `ai.admit` (AC-15).

**§7 Metrics (018a foundation; each PR adds its own).**
- `kernel.telemetry` gains a process `MeterProvider`. It exports OTLP when `otlp_endpoint` is set, and has an in-memory reader for tests. Attributes are allowlisted, the same rule as spans: class, provider, model, reason, outcome, and `tenant.id` only on the slots metrics.
- **Instruments:**
  - `abacus.schedule_to_start` (histogram per class, from a worker activity interceptor: `started_time - scheduled_time`);
  - `abacus.slots.in_use` and `abacus.slots.waiting` (018b);
  - `abacus.admission` (counter by outcome and reason) and `abacus.capacity_timeout` (018c).
- **Queue depth (D5):** the Temporal backlog per queue comes from the Temporal server's own metrics (cloud or self-hosted) in TASK-014. The app reports what it knows: waiting runs per class (`slots.waiting`). No polling of Temporal's API.

**§8 AC-5 (018a):** an integration test with the real Temporal container. It saturates the background pool (pool size 2, two long activities), dispatches an interactive workflow, and asserts that schedule-to-start is under 2 s. Test pool sizes come from settings.

**Protected paths this needs (approval file):**
- `backend/src/abacus/kernel/**`, `backend/src/abacus/worker/**`, `backend/src/abacus/modules/connections/**`, `backend/src/abacus/modules/agents/**`, `backend/src/abacus/ai_gateway/**`, `backend/migrations/**`;
- `backend/src/abacus_tools/quality/banned_patterns.py` and its test, `backend/src/abacus_tools/quality/schema_check.py`;
- `packages/api-client/**`, `.claude/skills/**`.

### Questions for approval
- **D1. Three PRs (018a, 018b, 018c), in that order?** *Recommendation: yes.* Each is reviewable, and 018a alone already protects interactive work.
- **D2. Waiting happens in the workflow on durable timers, not in activities?** *Recommendation: yes.* Waiting holds no worker slot. It means versioned workflow changes and new replay histories.
- **D3. The slot ledger and provider buckets are platform tables reached only through `SECURITY DEFINER` functions, not tenant tables under forced RLS?** *Recommendation: yes.* This changes spec §7 ("tenant-scoped, forced RLS"). Fair hand-out across firms needs to see every firm's waiters, which forced RLS forbids. The functions take the tenant from the session, never from an argument, and return only the caller's own result. Two entries are added to `schema_check`'s `NON_TENANT_TABLES`/`GLOBAL_TABLES`.
- **D4. Priority by reserved headroom, with deferrable agents one class lower?** *Recommendation: yes.* It is simple, works across processes, and can't exceed the limits.
- **D5. Queue depth comes from Temporal's server metrics (TASK-014), and the app reports waiting runs and schedule-to-start?** *Recommendation: yes.* It avoids polling Temporal.

### Steps
1. Design and interface contract, after the spec is approved.
2. Implementation.
3. Independent tests (ADR-078), reviews, `make check`, PR.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-07` — Created with SPEC-003 (draft) for founder review.
- `2026-10-07` — SPEC-003 approved. Design §1–8 and D1–D5 written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
- Design questions D1–D5 (above).

## Handoff
- **Current state:** design written; waiting for founder approval of D1–D5. Branch `task-018-work-classes`.
- **Exact next step:**
  1. When approved, record the approval and the protected paths in *Plan*.
  2. Write the approval file at the founder's instruction.
  3. Write the 018a interface contract.
  4. Implement 018a, then run the independent tests and reviews.
