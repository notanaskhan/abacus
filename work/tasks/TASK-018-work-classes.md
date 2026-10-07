---
id: TASK-018
title: Work-class queues and admission control
spec: SPEC-003
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16]
risk_zone: amber
status: in-progress
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
- [x] Plan approved by human (founder, 2026-10-07: D1–D5 as recommended)
- Approved by founder: paths `backend/src/abacus/kernel/**`, `worker/**`, `modules/connections/**`, `modules/agents/**`, `ai_gateway/**`, `backend/migrations/**`, `banned_patterns.py` and its test, `schema_check.py`, `packages/api-client/**`, `.claude/skills/**` (local approval file `work/approvals/TASK-018.yaml`, written at the founder's instruction).

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

### Interface contract: 018a (tests written independently, ADR-078)
Source: SPEC-003 AC-1–5, AC-15 (schedule-to-start) and AC-16, and design §2, §3, §7 and §8. Every test names its AC.

**`abacus.kernel.dispatch`**
- `WorkClass` is `Literal["interactive", "time_sensitive", "background", "batch"]`. `WORK_CLASSES` is those four, in that order.
- `queue_for(c)` returns `f"{settings().temporal_task_queue}-{c with '_' replaced by '-'}"`, for example `abacus-time-sensitive`. An unknown class raises `ValueError`.
- `register_work_classes(mapping)`:
  - an unknown class raises `ValueError`;
  - registering the same workflow again with the same class is a no-op;
  - registering it with a different class raises `ValueError`.
- `work_class_of(workflow)` raises `LookupError` for an unregistered workflow (AC-4).
- `await dispatch(Workflow, arg, *, id, id_reuse_policy, id_conflict_policy, execution_timeout=None)`:
  - starts `Workflow.run` on `queue_for(work_class_of(Workflow))` with the given ID and policies, through `kernel.temporal.temporal_client()`;
  - logs `dispatch.started` (`workflow`, `work_class`);
  - an unregistered workflow raises `LookupError` before contacting Temporal.

**Registrations (SPEC-003 Q1)**
- `connections.api.WORKFLOWS == {RetrievalWorkflow: "interactive"}`.
- `agents.api.WORKFLOWS == {ScreeningWorkflow: "time_sensitive"}`, taken from the screener's spec.
- Both are registered at import.
- `connections.retrievals` and `agents.screenings` start their workflows only through `dispatch`, keeping their existing ID, reuse and conflict policies and the retrieval's 6 h execution timeout.

**Agent specs (AC-4; ADR-105)**
- `AgentSpec` requires `work_class` (a `WorkClass`), `essential` (`bool`) and `cheaper_tiers` (a tuple of `Tier`; may be empty).
- A spec missing any of them, or with an unknown class, fails validation (`AGENTS` doesn't load).
- The screener has `time_sensitive`, `true` and `[]`.

**Worker (`abacus.worker.__main__`) (AC-1, AC-16)**
- `build_worker()` is replaced by `async build_workers(classes=WORK_CLASSES) -> list[Worker]`.
- It runs the same boot checks in the same order as before, then builds one `Worker` per class served, with `task_queue=queue_for(c)`, `max_concurrent_activities=settings().worker_max_activities[c]` and `max_concurrent_workflow_tasks=settings().worker_max_workflow_tasks[c]`. When `settings().serve_legacy_queue` is true (the default) it adds one more worker on `settings().temporal_task_queue`, using the interactive limits.
- Every worker registers every module's workflows and activities, with interceptors `[ReportingInterceptor(), ScheduleToStartInterceptor()]`.
- It configures tracing, metrics (`configure_metrics("abacus-worker")`) and error tracking.
- `classes_from(argv)`:
  - parses `--classes a,b` (default: all four);
  - drops duplicates and returns them in `WORK_CLASSES` order;
  - exits with argparse's error for an unknown or empty list.
- `run(classes)` enters every worker, runs the relay as before, and on exit calls `shutdown_tracing()`, `shutdown_metrics()` and `flush_errors()`.
- `main(argv=None)` passes `classes_from(argv or sys.argv[1:])` to `run`.
- Settings defaults:
  - `worker_max_activities` and `worker_max_workflow_tasks` are `{interactive: 50, time_sensitive: 50, background: 20, batch: 10}`;
  - `serve_legacy_queue` is `True`.

**DISPATCH-001 (AC-3)**
- It flags, in `src/abacus/*` except `kernel/dispatch.py` and `worker/__main__.py`:
  - any call named `start_workflow`, `execute_workflow` or `signal_with_start_workflow`;
  - any call with a `task_queue=` keyword.
- The repository is clean.

**Metrics (`abacus.kernel.metrics`) (AC-15, part)**
- `configure_metrics(service, reader=None)` is idempotent (first call wins). It installs a global `MeterProvider` whose only view keeps the attribute keys `{work_class, provider, model, reason, outcome, tenant.id}`; any other attribute is dropped. An OTLP reader is added when `otlp_endpoint` is set, at `otlp_url(endpoint, env, "metrics")`, with https outside local and test.
- `test_reader()` returns the process's `InMemoryMetricReader`, refused outside local and test.
- `shutdown_metrics()` flushes and shuts down.
- `ScheduleToStartInterceptor` records the histogram `abacus.schedule_to_start` (unit `s`, value `started_time - current_attempt_scheduled_time`, never negative) with `work_class` from the task queue: one of the four, or `legacy`.
- `kernel.telemetry._endpoint` is replaced by the public `otlp_url(raw, environment, signal="traces")`.

**AC-5 (integration, real Temporal container)**
- Saturate the background pool: `worker_max_activities["background"] = 1`, with a long-running activity holding it.
- Dispatch an interactive workflow.
- Assert that its first activity starts within 2 s.

**AC-16:** a workflow started on the legacy base queue completes, served by the legacy worker. The recorded v1 histories still replay.

**Existing tests that change (pins, not weakening):**
- `tests/unit/worker/*` (`build_worker` → `build_workers`, a list of workers);
- `tests/unit/agents/test_screening_contract.py` (the `WORKFLOWS` shape; `start_screening` now goes through `dispatch`);
- the integration fixtures that run a `Worker` on `QUEUE` and set `ABACUS_TEMPORAL_TASK_QUEUE`. Their workers must poll `queue_for(<class>)`, or the tests must use `build_workers`. This affects `test_retrieval_workflow.py`, `test_retrieval_api.py`, `agent_tests/test_screening_workflow.py`, `test_observability_flow.py` and `test_walls_runs.py`;
- `tests/unit/worker/conftest.py` already stubs `shutdown_metrics` alongside `shutdown_tracing`.

### Contract revision 1: 018a review fixes (supersedes the contract above where they differ)
- **Leaf module:** `WorkClass` and `WORK_CLASSES` live in `abacus.kernel.work_class`, re-exported by `kernel.dispatch`. `dispatch.work_class_of_queue(q)` returns the class or `None` (the legacy queue, or any other). `register_work_classes` takes `Mapping[type, WorkClass]`.
- **Registration lives beside the starter:**
  - `connections.retrievals.WORKFLOWS` (interactive) and `agents.screenings.WORKFLOWS` (the screener spec's class) are registered when those modules are imported, and re-exported as `api.WORKFLOWS`.
  - Importing `retrievals` or `screenings` on its own is enough to dispatch.
- **Settings:**
  - `worker_max_activities` and `worker_max_workflow_tasks` are replaced by `work_classes: dict[WorkClass, WorkClassLimits]`.
  - `WorkClassLimits` has `max_activities` and `max_workflow_tasks`, both at least 1, frozen, with extra fields forbidden.
  - Defaults: interactive 10/10, time_sensitive 10/10, background 5/5, batch 2/2, lowered for the database pool.
  - The settings are refused unless they hold exactly the four classes.
- **Worker:**
  - The legacy worker is added only when `serve_legacy_queue` is true and `interactive` is among the classes served.
  - The relay runs only in a process serving `interactive`.
  - `run`:
    1. starts `worker.run()` for every pool as a task, plus the relay task;
    2. waits for the signal or for any task to end;
    3. calls `shutdown()` on every worker together, then awaits the tasks;
    4. only then calls `shutdown_tracing()`, `shutdown_metrics()` and `flush_errors()`;
    5. re-raises the first task's exception; a pool or relay that ended before the signal without one raises `RuntimeError`.
- **Metrics:**
  - The allowlist is `{work_class, provider, model, reason, outcome}`; there is no `tenant.id` (018b adds a per-instrument view).
  - Exemplars are off (`AlwaysOffExemplarFilter`).
  - `test_reader` is renamed `in_memory_reader`.
  - `configure_metrics(service, reader)` raises `RuntimeError` when a reader is passed after the provider exists.
  - `ScheduleToStartInterceptor` and `SCHEDULE_TO_START` move to `abacus.kernel.temporal_metrics`, with work class `legacy` for a queue that isn't a class queue.
- **DISPATCH-001:**
  - It also flags any reference to these names, not only a call: `start_workflow`, `execute_workflow`, `signal_with_start_workflow`, `start_update_with_start_workflow`, `start_child_workflow`, `execute_child_workflow`, `create_schedule`, `ScheduleActionStartWorkflow` or `temporal_client`. That covers an attribute, a name, an import alias and a string constant (`getattr(c, "start_workflow")`).
  - It also flags any `from temporalio.client import ...`.
  - It still flags `task_queue=`.
  - Excluded files: `kernel/dispatch.py`, `kernel/temporal.py` and `worker/__main__.py`.
- **AgentSpec:** every entry of `cheaper_tiers` must be strictly cheaper than `tier` (small < medium < large), or the spec doesn't load.

### Interface contract: 018b caps (tests written independently, ADR-078)
Source: SPEC-003 AC-6–8, AC-13, AC-14 and AC-15 (slots), design §4–5 and D2–D3, and the founder decision of 2026-10-07 below. Every test names its AC.

**Database (migration 0013)**
- **Tables:** `work_slots`, `work_waiters` and `work_grants` are platform tables with no privileges for `abacus_app` or PUBLIC. `schema_check` lists them in `NON_TENANT_TABLES`, `GLOBAL_TABLES` and `TABLE_OWNERS` (`kernel.slots`).
- **Functions:** `work_slot_acquire(holder, engagement_id, class, firm_cap, engagement_cap, class_capacity, lease_seconds) -> (granted, reason, estimated_start_at)`, `work_slot_release(holder)` and `work_slot_renew(holder, lease_seconds) -> bool`.
  - All three are SECURITY DEFINER, with `search_path` pinned. EXECUTE is granted to `abacus_app` only.
  - Without `app.tenant_id` they raise (`insufficient_privilege`).
  - An invalid class or a negative cap raises `invalid_parameter_value`.
- **Acquire:**
  - It is idempotent per holder; a holder already holding renews and gets `(true, null, null)`.
  - Expired leases (database time) and waiters unseen for 5 minutes are reclaimed.
  - **Grant rule:**
    - a slot goes only while the class is under `class_capacity`;
    - the waiter must be the first eligible one: its firm under `firm_cap` and its engagement under `engagement_cap` in that class;
    - eligible waiters are ordered by their firm's latest grant in the class over the last 10 minutes (none first), then `waiting_since`, then holder.
  - **Not granted:** the reason is `firm_cap`, `engagement_cap` or `class_capacity`, from the caller's own counts only. The estimate is null when the class had no grants in the last 10 minutes.
  - A cap of 0 never grants.
- **Release** frees the slot and the waiter for the caller's tenant only, and is idempotent. A caller can never release or renew another tenant's holder.
- **Run columns:** `sync_runs` and `agent_runs` gain `queued_reason` (null, or one of `firm_cap`, `engagement_cap`, `class_capacity`, `provider_capacity`, `deferred`) and `estimated_start_at`. The app may update both. CHECK: a run that isn't `running` has both null.
- The migration is reversible.

**`abacus.kernel.slots`**
- `acquire(tenant, holder, engagement_id, work_class) -> SlotDecision(granted, reason, estimated_start_at)` passes the class's `settings().work_classes[c]` caps and `LEASE_SECONDS = 900`.
- `renew(tenant, holder) -> bool` and `release(tenant_id, holder)`.
- Each call commits on its own, with no audit event (founder decision 2026-10-07). UOW-001 and UOW-002 exempt only `kernel/slots.py`.
- `current_holder()` returns `"<workflow_id>:<workflow_run_id>"`. `current_class()` returns the class of the activity's task queue, or None.
- Every `acquire` increments the counter `abacus.slots.decisions` (`work_class`, `outcome` granted or waiting, `reason`) and logs `slot.acquired` or `slot.waiting` (`tenant_id`, `work_class`, `reason`).

**Settings:** `WorkClassLimits` gains `firm_cap` (≥0), `engagement_cap` (≥0), `class_capacity` (≥1) and `max_wait_seconds` (≥1).
| Class | Firm cap | Engagement cap | Class capacity | Max wait |
|---|---|---|---|---|
| interactive | 20 | 10 | 50 | 120 s |
| time_sensitive | 20 | 10 | 50 | 600 s |
| background | 10 | 5 | 20 | 21,600 s |
| batch | 5 | 2 | 10 | 86,400 s |

**Activities**
- **`retrieval.acquire_slot(RetrievalInput) -> SlotGrant(granted, max_wait_seconds)`** and **`screening.acquire_slot(RunInput)`**:
  - a run already ended, or an activity on a queue that isn't a class queue, gets `(True, 0)` and takes no slot;
  - otherwise they acquire, then mark the run queued with the reason and estimate, or running again with both null.
  - The mark is through the unit of work and audited `sync_run.queued`/`sync_run.resumed` (`agent_run.*` for screening) only when `queued_reason` changes, so repeated asks with the same reason write nothing.
- **`retrieval.release_slot`** and **`screening.release_slot`** release; they are a no-op off the class queues.
- Every retrieval stage and `screening.screen` renew the slot first.

**Workflows (behind `workflow.patched("work-slots")`)**
- **Retrieval** waits for its slot before `pull_raw`. **Screening** waits after `create_run` (a skipped screening takes no slot).
- `wait_for_slot` asks, then sleeps on durable timers with backoff from 1 s, jittered ×0.5–1.5 with `workflow.random()`, capped at `max(10, max_wait_seconds/300)`.
- When the class's `max_wait_seconds` has passed since the first ask, the run is failed with `capacity_timeout` (in `FAIL_CODES` of both modules).
- The slot is released in `finally` on every path.
- The v1 histories still replay. New histories `retrieval-v2-*` and `screening-v2-*` are recorded and must replay.

**API:** `RetrievalOut` gains `queued_reason` and `estimated_start_at`. A running run with a `queued_reason` is reported as `status: "queued"`, and is never shown as `running` while queued (AC-13).

**Existing tests that change (pins)**
- Activity-order assertions in `test_retrieval_workflow.py` and `agent_tests/test_screening_workflow.py` (the slot activities are added).
- The activity count, and the `RetrievalOut` field set in `test_retrieval_api.py`.
- The update-column map in `test_schema_check_db.py`.
- `test_ac20_every_input_and_result_in_the_history_is_encrypted`: Temporal's `core_patch` marker and the `TemporalChangeVersion` search attribute are written by Temporal itself in plain JSON and hold only patch names. The test must allow exactly those, and assert they contain nothing but patch IDs.

### Contract revision 1 (018b): review fixes, superseding the 018b contract where they differ
- **Ledger keys:** `work_slots` and `work_waiters` are keyed `(tenant_id, holder)`, and every statement filters by the session's tenant. A holder ID colliding with another firm's touches only the caller's rows and never raises across firms.
- **Bounds:** acquire refuses (`invalid_parameter_value`) caps outside 0–10,000, `class_capacity` outside 1–10,000, and a lease outside 1–3,600 s; renew bounds the lease the same way. A firm with `4 × max(firm_cap, 1)` waiters in a class gets `(false, 'firm_cap', null)` for a new holder, without being added.
- **Function settings:** each function sets `lock_timeout = 5s` and `statement_timeout = 10s`, and pins `search_path = pg_catalog, public, pg_temp`; every relation is written as `public.*`.
- **Liveness and the estimate:** only waiters seen in the last 3 minutes are eligible, or count for the estimate. The estimate is `date_trunc('minute', now) + ceil((ahead + 1) / rate)` minutes, where `ahead` is the live waiters before the caller in the class and `rate` is the class's grants per minute over 10 minutes.
- **RLS:** the ledger tables have row-level security enabled with no policy, and no `abacus_app` privileges.
- **`schema_check`:** every SECURITY DEFINER function must be in `DEFINER_FUNCTIONS`, owned by `abacus_owner`, with `search_path=pg_catalog, public, pg_temp`, executable by `abacus_app`, and not by PUBLIC or the bypass roles.
- **Ending a run:** `finish` (sync runs) and `finish_run` (agent runs) clear `queued_reason` and `estimated_start_at`. A run queued, then failed `capacity_timeout` or cancelled, ends cleanly.
- **`kernel.slots`:**
  - `system_tenant(tenant_id)` is the firm's slot context.
  - `keep(tenant, engagement_id, work_class)` runs before every retrieval stage and before `screen`, inside the activity's error mapping. It renews the slot, re-acquires it if the lease was reclaimed, and if none is free logs `slot.lost` (warning) and lets the stage run.
- **Workflows:**
  - Between asks, the backoff is capped at 60 s, jittered by ×0.5–1.5.
  - Asks use `ActivityCancellationType.WAIT_CANCELLATION_COMPLETED`.
  - Release (`_release`) takes at most 5 attempts within 1 hour, and its `ActivityError` is swallowed: a failed release never changes the run's outcome.
  - The two modules' `wait_for_slot` bodies are identical (test it, comparing the ASTs).
- **API:** `RetrievalView.reported_status` is `queued` for a running run with a reason, and `RetrievalOut.status` comes from it. Internal checks keep using the stored `status`.
- **SPA:** the board treats `queued` like `running`: it keeps polling and keeps the button disabled. It shows "Queued: expected to start by HH:MM", or "Queued: waiting for capacity" when there's no estimate.
- **Histories:** v2 is re-recorded. Also needed: v2 recordings with at least two asks and timers, with `capacity_timeout`, and with a cancel while waiting (extend `abacus_tools/workflows/record_*`). The replay tests run over every `*-v2-*` file.
- **More pins:** `apps/web/src/screens/Board.test.tsx` (the fixtures gain `queued_reason`/`estimated_start_at`; add a queued case).

### 018c detailed design (within approved design §6 and D4)
- **Migration 0014.**
  - Platform table `provider_capacity`:
    - columns: `(provider, model)` as the PK, `rpm`, `tpm`, `requests_left`, `tokens_left` (numeric), `refilled_at`, `blocked_until`;
    - no app privileges and RLS enabled with no policy, the same pattern as the slot ledger.
  - SECURITY DEFINER functions:
    - `capacity_admit(provider, model, rpm, tpm, reserve_pct, tokens) -> (admitted, retry_after_seconds)`. It requires a tenant session, bounds its inputs, and refills by elapsed database time up to `rpm`/`tpm`. It takes one request and `tokens` only if both buckets stay above `reserve_pct` of their size, and it is never admitted while `blocked_until` is in the future.
    - `capacity_block(provider, model, seconds)`. It sets `blocked_until`, raising it only, and empties both buckets.
    - Both are added to `DEFINER_FUNCTIONS`, `NON_TENANT_TABLES`/`GLOBAL_TABLES` and `TABLE_OWNERS` (`ai_gateway`).
  - `usage_records.outcome` gains `rate_limited`.
- **Settings.**
  - `provider_limits: dict[model, {rpm, tpm}]`, set at 80% of the provider's limits (Q5). Generous defaults for the fake models.
  - `WorkClassLimits.admission_reserve_pct`: interactive 0, time-sensitive 0, background 25, batch 50 (D4).
- **Gateway.**
  - **New fields:** `GatewayCall` gains `work_class`, `essential` and `cheaper_tiers`. The screening service passes them from its spec.
  - **Admission:** before each attempt, `call()` admits under an `ai.admit` span. The reserve is the class's own if the call is essential, otherwise the next class's (D4). The token estimate is the input estimate plus `max_output_tokens`.
  - **If not admitted:** it tries each `cheaper_tiers` model in turn (AC-11; none today). If none is admitted, it raises `NotAdmitted(reason, retry_after)`. The reason is `deferred` when a background or batch call was refused only by its reserve, otherwise `provider_capacity`.
  - **Rate limits:** `ProviderError` gains `rate_limited` and `retry_after`. A rate-limited response calls `capacity_block`, records usage `rate_limited` with nothing spent, and raises `NotAdmitted("provider_capacity", retry_after)`. The gateway never retries it itself (AC-12).
  - **Fail closed:** if the capacity store errors, the call raises `NotAdmitted("provider_capacity", 30)` and is never admitted unmetered.
  - **Metric:** the counter `abacus.admission`, with `provider`, `model`, `work_class`, `outcome` and `reason`.
- **Screening.**
  - `screen` turns `NotAdmitted` into a non-retryable `ApplicationError("NotAdmitted", reason, retry_after)`. Before raising, it marks the run queued with the reason and `estimated_start_at = now + retry_after`. Once admitted, it marks the run resumed.
  - Behind `patched("admission")`, the workflow catches it, sleeps for `retry_after` with jitter (at least 1 s and at most 60 s), and calls `screen` again. Past the class's maximum wait (from the slot grant), the run fails `capacity_timeout`.
- **F1 (review question): wait for capacity while holding the slot.** Recommended. The slot stands for the run's work in progress. Releasing it to wait would let the firm start more work that needs the same provider, and a run would queue twice. A slot grant clears only slot reasons (`firm_cap`, `engagement_cap`, `class_capacity`), and admission clears only `provider_capacity`/`deferred`, so no queued and resumed entries flap in the audit trail.

### Interface contract: 018c admission (tests written independently, ADR-078)
Source: SPEC-003 AC-9–12, AC-13 (admission reasons), AC-14, AC-15 (admission), design §6 and D4, and the "018c detailed design" above (F1 as recommended). Every test names its AC.
- **Migration 0014.**
  - `provider_capacity` is a platform table with no app privileges and RLS enabled with no policy. It is in `NON_TENANT_TABLES`, `GLOBAL_TABLES` and `TABLE_OWNERS` (`ai_gateway`).
  - `capacity_admit(provider, model, rpm, tpm, reserve_pct, tokens) -> (admitted, retry_after_seconds)`:
    - it needs a tenant session;
    - arguments must be `rpm` 1–1,000,000, `tpm` 1–100,000,000, `reserve_pct` 0–99 and `tokens` 1–`tpm`, otherwise `invalid_parameter_value`;
    - it creates the bucket full on first use and refills by elapsed database time, at most one minute's worth;
    - it admits only if `requests − 1` and `tokens_left − tokens` both stay at or above `reserve_pct`% of the limit, and never while blocked;
    - when it refuses, `retry_after` is the time to refill above the reserve, from 1 to 60 s, or the remaining block.
  - `capacity_block(provider, model, seconds)`: seconds must be 1–3,600. It empties both buckets and moves `blocked_until` later, never earlier.
  - Both functions are SECURITY DEFINER with the pinned search path and timeouts. They are in `DEFINER_FUNCTIONS`, and EXECUTE is granted to the app only.
  - `usage_records.outcome` allows `rate_limited`. The downgrade refuses while such rows exist.
- **Settings.**
  - `model_provider` (`"fake"`).
  - `provider_limits: dict[model, ProviderLimits(rpm, tpm)]` (the fake models: 600 and 1,000,000).
  - `WorkClassLimits.admission_reserve_pct`: interactive 0, time_sensitive 0, background 25, batch 50.
- **`ai_gateway.admission`.**
  - `NotAdmitted(reason, retry_after)`.
  - `reserve_pct(work_class, essential)`: a non-essential call takes the next class's reserve (interactive → time_sensitive → background → batch, and batch → batch).
  - `refusal_reason(c)`: `deferred` for background and batch, `provider_capacity` otherwise.
  - `admit(tenant, model, work_class, essential, tokens) -> (admitted, retry_after)`. An unknown model, or an unreachable bucket, gives `(False, 30)`.
  - `block(tenant, model, seconds)`, with `seconds` clamped to 1–3,600.
  - Both commit with no audit event (UOW-001/002 exempt this file).
  - Counter `abacus.admission` (`provider`, `model`, `work_class`, `outcome` admitted or refused, `reason`). Logs `admission.refused`, `admission.unavailable` and `provider.rate_limited`.
- **Gateway.**
  - `GatewayCall` requires `work_class` and `essential`, and has `cheaper_tiers` (default empty).
  - Before every attempt, after the budget check, the call is admitted under an `ai.admit` span, with tokens = the input estimate + `max_output_tokens`. Attempt 1 may step down through `cheaper_tiers`, and cost and usage follow the admitted tier. If nothing admits, it raises `NotAdmitted` with the smallest `retry_after`.
  - `ProviderError(rate_limited=True, retry_after=…)`: block for `retry_after` (or 30 s), record usage `rate_limited` with nothing spent, and raise `NotAdmitted("provider_capacity", wait)`. It is never retried within the call.
  - Other provider errors are unchanged.
- **Screening.**
  - The service passes the spec's `work_class`, `essential` and `cheaper_tiers`.
  - The `screen` activity first clears an admission reason with `mark_queued(None)`. On `NotAdmitted` it marks the run queued (reason, now + `retry_after`) and raises a non-retryable `ApplicationError` of type `NotAdmitted`, with details `(reason, retry_after, max_wait_seconds of the class)`.
  - Behind `patched("admission")`, the workflow sleeps `retry_after` × jitter (0.5–1.5), clamped to 1–60 s, then screens again. When the class's maximum wait has passed since the first refusal, it fails the run `capacity_timeout`. The slot is held throughout (F1).
- **Pins:** every `GatewayCall(...)` in tests gains `work_class` and `essential`. The 018b pins still apply.

### Contract revision 1 (018c): review fixes, superseding the 018c contract where they differ
- **0014.**
  - Arithmetic is numeric (no integer overflow up to `tpm` 1e8 at a 99% reserve).
  - NULL arguments are refused, and so is a model name not matching `^[a-z0-9][a-z0-9._-]{0,99}$`.
  - At most 1,000 buckets (`program_limit_exceeded`).
  - `capacity_block` updates an existing bucket only and never inserts.
  - The tenant check casts to uuid.
  - The outcome CHECK is added `NOT VALID`, then validated.
- **`admission.admit`.** It raises `CallTooLarge` (a ValueError) when `tokens > tpm × (100 − reserve) / 100`, and never clamps. It logs `admission.unconfigured` for a model with no limits.
- **Gateway.**
  - Background and batch calls are never stepped down (deferred first, ADR-072).
  - On a rate limit, `retry_after` must be finite (otherwise 30), is rounded up, and is clamped to 1–3,600. A failing `block` is logged (`admission.block_failed`) and the call still raises `NotAdmitted`. The reason is `refusal_reason(work_class)`.
  - `NotAdmitted` doesn't mark the `ai.call` span as an error (`ai.status = not_admitted`, `ai.admission_reason`).
  - `CallTooLarge` maps to terminal code `context_too_large` in screening.
  - `check_provider_limits()` (worker boot) refuses to start outside local and test if any `MODELS` entry has no limits.
- **Screening activity.**
  - It no longer clears the reason at the start. It clears (`mark_queued(None)`) only after `screen` returns, and repeated refusals with the same reason write nothing.
  - Only an `ApplicationError` of type `NotAdmitted` crosses as it is; others become class-name-only retryable errors.
- **Workflow.**
  - `waiting_from = workflow.now()` is taken before the slot wait, and the class's maximum wait is measured from it (slot plus admission).
  - The admission sleep is `max(retry_after, backoff) × jitter(0.5–1.5)`, at most 60 s, with backoff from 5 s doubling to 60 s.
- **Histories still needed.** Screening v3 recordings with refused, slept then admitted, with `capacity_timeout` during admission, and with a cancel while sleeping. v1 and v2 must replay against this code.

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
- `2026-10-07` — 018c reviews (security B1 integer overflow, B2 audit flapping, S1–S7, N1–N4; architecture B1 flapping, S1 ADR-072 order, S2 history and floor, S3 total wait, S4 block masking, S5 oversize, S6 AC-10, nits). All fixed or recorded; SPEC-003 amended. The security reviewer agreed with the UOW exemption for `admission.py`. Contract revision 1 (018c).
- `2026-10-07` — 018c implemented on `task-018c-admission` (stacked on 018b): migration 0014, `ai_gateway.admission`, gateway admission and cheaper tiers, rate-limit block, screening wait behind `patched("admission")`, settings, docs and contract. Waits for 018b's tests and merge.
- `2026-10-07` — 018b reviews. Security: H1 holder keys, H2 estimate, M1–M7. Architecture: B1 a queued run couldn't end, B2 the estimate, B3 the SPA showed queued as finished, B4 replay coverage, S1–S10. Fixed: H1, M1–M7 (S1–S3, S5, S7, S9, S10), B1, B3, N1, N2 (indexes and keys) and N4. The estimate is set on queueing and on a reason change only (B2/H2: refreshing it would need an audit event per ask; spec amended); S6 spec amended. Handed to the test author: the B4 recordings, the S8 identical-loop test, and the pins. Contract revision 1 (018b).
- `2026-10-07` — 018a merged (PR #26). 018b implemented: migration 0013 (slot ledger and functions; run queued columns), `kernel.slots`, slot activities and workflow waits behind `patched("work-slots")`, `capacity_timeout`, the queued API status, the slots metric and logs, and v2 histories. Founder decision: the ledger commits without audit events. Contract 018b written.
- `2026-10-07` — Independent tests cherry-picked (4ccb451; about 220 tests and about 400 DISPATCH-001 cases; no product bugs). Unit and property: 8,175 passed with the compose DB stopped. 018a PR opened.
- `2026-10-07` — 018a reviews: security (S1 DISPATCH-001 sidesteps, S2 legacy pool in non-interactive processes, S3 relay in every process, S4 `tenant.id`, S5 exemplars, S6–S9) and architecture (A1 a dead pool unnoticed, A2 serial shutdown, A3 telemetry shut before drain, A5 settings by class, A6–A7 kernel layering, A9 registration beside the starter, A11–A17). All fixed except A16 (the glossary is protected and outside this approval). Contract revision 1.
- `2026-10-07` — Design approved (D1–D5). 018a implemented: `kernel.dispatch`, `kernel.metrics`, the per-class worker pools and legacy queue, DISPATCH-001, the agent spec fields, ADR-105, and docs (kernel README, temporal reference, skill). Static gates pass on `src`; 11 unit tests and the integration fixtures pin the old worker and queue (handed to the test author).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The slot ledger commits without audit events (UOW-001/002 exempt `kernel/slots.py` only); a run's queued and resumed transitions are audited | Polling every few seconds would flood the audit trail; SPEC-003 §14. Founder decision 2026-10-07 | No (recorded here and in `kernel/slots.py`) |
| A waiting run stays `running` in the database with `queued_reason`; the API reports `queued` | Avoids widening every status check and trigger; the API still never shows waiting work as running (AC-13). Design §5 revised | No |
| The wait loop is copied into each module's `workflows.py` | ADR-017's import contract bars workflows from importing the kernel | No |
| Slot hand-out is poll-based: a free slot goes to the first live waiter when it next asks (at most about 90 s), so capacity can sit idle briefly. Waiters silent for 3 minutes stop holding others up | Fairness without a cross-process signal; SPEC-003 §12 (018b review S5) | No |
| `class_capacity` added as a queued reason; SPEC-003 amended (storage of the queued status, the estimate, screening's API as a follow-up) | 018b review S6 | No (spec amended) |
| Provider capacity commits without audit events, like the slot ledger (UOW exemption for `ai_gateway/admission.py`) | The same operational-ledger reasoning as the founder's slot decision; the security review agreed; the founder was told (2026-10-07) | No |
| The provider bucket is shared by every firm, with no per-firm share in admission | Per-firm fairness comes from the slot caps (0013). Limits are trusted app input. Accepted risk (security review S2) | No |
| A batch admission wait of up to 24 h at a 60 s cap is about 14k history events (under the 51k limit, above the 10k warning) | No batch agents exist yet; `continue_as_new` when one does | No |
| A screen waiting for provider capacity keeps its slot (F1) | Releasing it would let the firm start more work needing the same provider; no audit flapping | No |
| No per-firm slots-in-use gauge; per-firm detail is in `slot.*` logs | A process-local gauge is wrong across processes, and the metrics allowlist carries no tenant ID | No |

## Gotchas and discoveries
- 018b: workflows can't import `kernel.dispatch` (WF-001), so a workflow's class must come from its input or `workflow.info().task_queue` (`work_class_of_queue`); a legacy-queue workflow has no class and skips slots (it runs behind `patched` anyway).
- Deploy order: workers before the API, or dispatched work waits for pollers on the new class queues.
- Database pool: worker concurrency now totals 27 (plus 10 legacy) per process against SQLAlchemy's default pool (5 + 10); size the pool with TASK-014.
- The design text says `dispatch(workflow_name, ...)` and `cheaper_tiers` default `[]`; the contract (the workflow class; required) supersedes it.

## Questions for the human
- Glossary entries "work class" and "essential" (A16): the glossary is protected and not in this task's approval.

## Handoff
- **Current state:** 018b implemented on `task-018b-slots` (`task-018b-caps` is stale: cut from the pre-merge 018a branch; ignore it).
- **Exact next step:**
  1. Run the independent tests on `task-018b-slots-tests` from the 018b contract, including the pins.
  2. Run the security and architecture reviews.
  3. Cherry-pick, fix, and run the full suite with the compose DB stopped.
  4. Open the PR.
  5. Then 018c, admission (design §6).
