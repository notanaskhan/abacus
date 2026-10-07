---
id: SPEC-003
title: Work-class queues and admission control
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-071, ADR-072, ADR-017, ADR-069, ADR-073, ADR-075, ADR-090, ADR-093, ADR-094, ADR-047]
related_specs: [SPEC-000]
created: 2026-10-07
updated: 2026-10-07
---

> **Amended 2026-10-07 during TASK-018 (018b)**:
> - **Queued status storage:** a run waiting for a slot stays `running` in the database, with `queued_reason` and `estimated_start_at`. Every API reports it as `queued`, never `running` (AC-13 holds).
> - **New reason:** `class_capacity` (the whole class is full) joins the reasons.
> - **Screening:** queued screening runs are recorded on the agent run. There is no API for agent runs yet, so showing them is a follow-up.
> - **No audit for slot bookkeeping:** the slot ledger commits without audit events (founder decision). The run's queued and resumed transitions are audited.
> - **Admission (018c):**
>   - **Interface:** `NotAdmitted(reason, retry_after)` is raised by `call()`. The wait loop lives in the workflow, not in an `admit` context manager. An unreachable bucket refuses at once (the wait is the workflow's).
>   - **Metrics:** one counter, `abacus.admission`, with outcome and reason.
>   - **Priority within a class:** essential before deferrable is by reserve, not by queue order. Waiting callers ask again, and whoever finds capacity first goes.
>   - **Reasons:** background and batch work is deferred (never stepped down); interactive and time-sensitive work steps down to a cheaper tier, then waits as `provider_capacity`.
>   - **Maximum wait:** a class's maximum wait covers the whole wait, for a slot and then for admission.
> - **Estimate:** set when the run is queued and whenever its reason changes. It is rounded up to whole minutes and comes from the class's queue position and grant rate only.

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
All asynchronous work is sorted into four work classes: interactive, time-sensitive, background and batch. Each class runs on its own Temporal task queue with its own worker pool. Per-firm and per-engagement concurrency caps keep one firm or engagement from starving the rest (ADR-071). Model calls are admitted through the AI gateway against tracked provider capacity, in priority order. Under pressure the gateway steps down visibly, and never fails silently or storms the provider with retries (ADR-072). This is the Execution layer of Phase 1 §5.3, "all four work classes and admission control".

## 2. Problem and context
Today every workflow runs on one task queue (`settings().temporal_task_queue`, default `abacus`), served by one worker process. Each dispatch site calls `client.start_workflow(..., task_queue=settings().temporal_task_queue)` itself: `connections/retrievals.py` for a retrieval a person starts, and `agents/screenings.py` for screening started by the outbox. The gateway enforces cost budgets but tracks no provider capacity, so a rate-limit response is just a `provider_error`.

That is fine for one synthetic firm. In busy season it is not:
- a firm's bulk sync or a replay would sit in front of a person waiting on a retrieval;
- one large engagement could take every worker slot;
- the first provider rate limit would fail runs or set off retries.

Fixing this now, with two workflows, costs much less than retrofitting it across ten.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm user | Starts interactive work (a retrieval); sees the status and estimate of queued work |
| Workflows and agents | Declare a work class; are dispatched to its queue and admitted for model calls |
| Platform operator | Sets queue sizes and the caps per firm, engagement and provider; watches queue depth and admission |

## 4. Goals and non-goals
**Goals**
- Four work classes, each with its own task queue and worker pool. Every workflow and agent declares its class.
- One dispatch function (`dispatch`) is the only way to start a workflow, and it routes by the declared class. Nothing else calls `start_workflow`.
- Per-firm and per-engagement concurrency caps, applied across classes, with fair ordering among firms.
- Gateway admission control: per provider and model token buckets (requests and tokens per minute) shared by every process. Admission is by class priority and never exceeds the configured limits.
- Degradation under pressure, in the ADR-072 order: defer batch, defer background, cheaper tier where evaluations allow, then queue with a visible status and estimate.
- Rate-limit responses from a provider are fed back into the bucket, never retried in a loop.
- Metrics: queue depth and schedule-to-start latency per class (ADR-094), and admission decisions.

**Non-goals**
- The budget hierarchy and metering of ADR-069 (soft and hard spend limits, anomaly alerts), which need their own spec. This spec only reads the agent's essential or deferrable flag.
- A second model route or failover between routes (ADR-073).
- The December load test at real volumes (ADR-075). This spec adds a scaled-down latency test in CI (AC-5) that the load test later reuses.
- Autoscaling worker pools, and Terraform for them (TASK-014).
- An operator UI. Caps and limits are settings.
- New user-facing screens. Queued status is exposed on the existing run resources (§8).

## 5. User stories and acceptance criteria
### Story 1: As a firm user I want my request to run promptly even when the platform is busy, so that I'm never stuck behind bulk work
- **AC-1** Given the four classes, when the worker starts, then it polls one task queue per class it is configured to serve (`<base>-interactive`, `<base>-time-sensitive`, `<base>-background`, `<base>-batch`), each with its own concurrency limits.
- **AC-2** Given a workflow registered with a work class, when it is started through `dispatch`, then it runs on that class's queue. Its activities run there too, unless an activity declares otherwise.
- **AC-3** Given any code outside `abacus.kernel.dispatch` that calls `start_workflow`, `execute_workflow` or passes `task_queue=`, then a static rule (DISPATCH-001) fails the build.
- **AC-4** Given a workflow or agent spec without a work class, then it can't be registered or loaded: the worker and the spec loader raise at import.
- **AC-5** Given the background pool saturated with long-running work, when a person starts a retrieval, then the retrieval starts within the interactive schedule-to-start target (Q4).

### Story 2: As a firm I want a fair share, so that another firm (or one engagement) can't starve my work
- **AC-6** Given a firm at its concurrency cap for a class, when it dispatches more work of that class, then the work waits, queued with a visible status, until a slot frees. Other firms' work in the same class proceeds.
- **AC-7** Given one engagement at its per-engagement cap, then other engagements of the same firm still run, up to the firm cap.
- **AC-8** Given several firms waiting for slots in one class, when slots free, then they go to firms in fair order (Q3), not in arrival order of the whole queue.

### Story 3: As the platform I never exceed a provider's limits, and degrade visibly
- **AC-9** Given a provider and model bucket configured with limits per minute, when concurrent callers in several processes request admission, then the admitted requests and tokens never exceed the limits in any window.
- **AC-10** Given contention for a bucket, then admission goes by class priority: interactive, then time-sensitive, then background, then batch. Within a class, essential agents are admitted before deferrable ones (ADR-069).
- **AC-11** Given the bucket below its pressure thresholds (Q5), then batch work is deferred first and background work second. An agent whose spec lists a cheaper tier that passed its evaluation suite steps down to it. Anything else waits, with a status and estimate. Each step is logged and counted.
- **AC-12** Given a provider rate-limit response (HTTP 429 or the provider's equivalent), then the gateway drains the bucket for the time the provider asks for, and does not retry the call itself. The calling activity waits for admission again, with no busy loop.
- **AC-13** Given work waiting for a slot or for admission, then its run shows status `queued` with a reason (`firm_cap`, `engagement_cap`, `class_capacity`, `provider_capacity` or `deferred`) and an estimated start. Nothing waiting is shown as `running` or `failed`.
- **AC-14** Given work that has waited longer than its class's maximum wait (Q6), then it ends as failed with code `capacity_timeout`, and is never dropped silently.

### Story 4: As an operator I can see and tune it
- **AC-15** Given the worker and the gateway running, then queue depth per class, schedule-to-start latency per class, slots in use per firm, and admission decisions (admitted, deferred or refused, by reason) are exported as metrics with identifiers only (ADR-094).
- **AC-16** Given workflows still open on the old single queue when this ships, then they finish there. A worker keeps polling the legacy queue until none remain (§19), and recorded histories still replay (ADR-090).

## 6. Behaviour and flows
**Happy path (a retrieval)**
1. A person calls `POST /v1/engagements/{id}/retrievals`. The service calls `dispatch("retrieval", input, id=..., ctx=...)`.
2. `dispatch` looks up the workflow's class (`interactive`) and starts it on `<base>-interactive`.
3. The first activity takes a concurrency slot for (firm, class) and (engagement, class), and releases it when the activity ends. If either is full, the activity doesn't run its stage: the run is marked `queued` and waits for a slot (§12).
4. A model-calling activity enters `gateway.admit(...)`, which takes request and token capacity from the provider and model bucket by priority, then calls the model.

**Alternate paths**
- Under pressure (AC-11), batch and then background admissions are deferred. Their runs show `queued`, with reason `deferred` and an estimate.
- A rate-limit response drains the bucket (AC-12), and waiting callers resume in priority order.
- Work waiting past its class's maximum ends `failed`, with `capacity_timeout` (AC-14).

**Initial class assignment** (Q1)
| Workflow or agent | Class | Why |
|---|---|---|
| `retrieval` started by a person | interactive | A person is waiting on it |
| `screening` (`evidence.screener`) | time-sensitive | SLO: interactive screening 95% within 30 s (ADR-093); nobody is blocked in the same request |
| Scheduled syncs, change detection (later) | background | — |
| Replays, backfills, evaluation runs (later) | batch | — |

**State transitions** (retrieval run and screening result)
| From | Event | To | Who can trigger |
|---|---|---|---|
| (none) | dispatch | queued | system |
| queued | slot and admission granted | running | system |
| running | waits for admission | queued | system |
| queued | maximum wait exceeded | failed (`capacity_timeout`) | system |

## 7. Domain and data changes
- **Kernel:**
  - `WorkClass` (`interactive`, `time_sensitive`, `background`, `batch`);
  - `dispatch(...)`;
  - the queue name per class, `<temporal_task_queue>-<class>`.
- **Module registries:** `WORKFLOWS` becomes a map from workflow to class, or each workflow class carries a `work_class` attribute (the task chooses).
- **Agent specs (ADR-047):**
  - a new `work_class` field (one of the four);
  - the ADR-069 essential or deferrable flag (field name: Q2);
  - an optional `cheaper_tiers` list, used only when the evaluation suite has passed at that tier (empty for `evidence.screener` today).
- **New table `work_slots`** (platform-owned, tenant-scoped, forced RLS):
  - columns: `tenant_id`, `engagement_id` (nullable), `work_class`, `holder` (workflow and activity ID), `acquired_at`, `lease_until`;
  - slots are released on completion; an expired lease is reclaimed.
  - This applies if Q3 chooses database slots.
- **Gateway capacity state** (Q5):
  - a token bucket per (provider, model) holding requests per minute and tokens per minute;
  - shared by every process, so it is not in memory.
- **Run statuses:** retrieval runs and screening results gain the status `queued` with `queued_reason` and `estimated_start_at`. Status changes are forward-only, as today.
- **Failure codes:** `capacity_timeout` added to both workflows' failure codes (versioned, ADR-090).
- **Migrations:** additive. Existing rows keep their statuses.

## 8. Interfaces
**Module interfaces**
| Name | Purpose |
|---|---|
| `kernel.dispatch(workflow, input, *, id, tenant_id, engagement_id, id_policy...)` | The only way to start a workflow; routes by the registered class |
| `ai_gateway.admit(attribution, work_class, essential, estimate)` | Async context manager; returns when capacity is granted, or raises `CapacityTimeout` |
| `kernel.slots.hold(tenant, engagement_id, work_class)` | Async context manager taking firm and engagement slots (if Q3 chooses database slots) |

**API changes:** existing GETs of retrieval runs and screening results return `status: "queued"`, `queued_reason` and `estimated_start_at` (nullable). No new endpoints. The client is regenerated.

**Worker:** `python -m abacus.worker --classes interactive,time_sensitive` selects which pools the process serves. The default is all four, which is how `make dev` runs it.

## 9. Authorisation and tenancy
- **Tenant scoping:** slots are tenant-scoped rows under forced RLS. Provider capacity is platform-wide by nature and holds no tenant data, only provider, model and counts.
- **Who can do what:** no new matrix actions. Dispatch happens inside services that have already authorised (a retrieval: `evidence.upload`; screening: a system context).
- **Engagement-level access:** unchanged. Queued status is read through the existing authorised routes.
- **Ethical walls:** unchanged. A queued run acting for a walled person is denied at its next authorised step (SPEC-002 AC-7).
- **Client-side access:** none.

## 10. AI behaviour
No new model calls. Admission wraps every existing gateway call. The cheaper-tier step-down only applies to an agent whose spec lists a tier with a passing evaluation run; none qualifies today.

## 11. Integrations
- **External systems:** Temporal (task queues, worker pools), and the model provider's rate limits.
- **Rate limits and quotas:** each provider and model's limits are settings, kept below the provider's published or contracted limits (Q5).
- **Retries and backoff:** activities waiting for a slot or for admission do not count as failed attempts. They poll with backoff and jitter, or are signalled (task choice). A 429 never triggers an immediate retry.
- **Idempotency:** `dispatch` keeps each workflow's ID policies. Slot acquisition is idempotent per holder.
- **Failure behaviour:** while slots or capacity are unavailable, users see `queued` with an estimate. If the wait exceeds the class maximum, the run fails `capacity_timeout`.

## 12. Edge cases and failure modes
- **Worker crash while holding a slot:** the lease expires and the slot is reclaimed. A lease is renewed by the activity heartbeat.
- **Deploy while queued:** waiting is held in activity state or the database, never in process memory. A restart resumes waiting.
- **Old single-queue workflows:** they finish on the legacy queue (AC-16).
- **A cap of zero** (an operator pausing a firm): the firm's work stays queued with reason `firm_cap`. It does not fail until the maximum wait.
- **Clock skew between workers:** buckets and leases use database time, not the worker clock.
- **One engagement with very long runs:** it holds only its own engagement's slots, which stay under the firm cap.
- **The gateway's capacity store is unavailable:** fail closed. Admission waits and is then refused as `provider_capacity`, never admitted unmetered.
- **Estimate unknown** (no recent throughput): `estimated_start_at` is null, and the status still says `queued`.

## 13. Security and privacy
- **Data classification:** slots and buckets hold identifiers and counts only (internal). No client data.
- **PII:** none.
- **Secrets:** none new.
- **Threats considered:**
  - one tenant starving others, whether deliberately or through a runaway (mitigated by firm and engagement caps);
  - denial of wallet through retry storms (mitigated by admission and no retry on 429);
  - a tenant inferring another tenant's load from estimates (mitigated: an estimate is derived from the class's queue position and throughput, never other firms' identities or counts).
- **Mitigations:** as above. DISPATCH-001 prevents bypassing the queues.

## 14. Audit trail and evidence integrity
- **Actions logged:** queueing and admission are operational, not domain decisions, so they are logged and metered but not audit events. A run that ends with `capacity_timeout` records its failure through the existing audited `fail` path.
- **Provenance:** unchanged.
- **Immutable:** run status transitions stay forward-only.

## 15. Observability
- **Logs:**
  - `dispatch.started` (workflow, class, IDs);
  - `slot.waiting` and `slot.acquired`;
  - `admission.deferred` and `admission.refused` (provider, model, class, reason);
  - `provider.rate_limited`.

  IDs only.
- **Metrics (ADR-094, "queue depth per work class"):**
  - queue depth and schedule-to-start per class;
  - slots in use per firm and class;
  - bucket fill per provider and model;
  - admissions by outcome and reason;
  - `capacity_timeout` count.
- **Traces:** waiting for admission is a span (`ai.admit`) inside `ai.call`. Dispatch continues the caller's trace (TASK-013).
- **Alerts:** interactive schedule-to-start above target for 5 minutes; any `capacity_timeout`; a bucket exhausted for more than 10 minutes. Paging only on the SLO burn (ADR-093).

## 16. Performance and scale
- **Expected volumes (busy season, ADR-075):** tens of firms, dozens of engagements each. Thousands of retrievals and screenings an hour at peak.
- **Latency targets:** interactive schedule-to-start under 2 s at p95 (Q4). Screening completes within 30 s at p95, with time-sensitive priority (ADR-093).
- **Overhead:** slot acquire and release is one indexed write each. Admission is one atomic database update per call. Neither adds a database round trip per workflow step beyond that.
- **Limits:** caps and bucket sizes are settings per environment.

## 17. UX
No new screens. Wherever the SPA shows a retrieval or screening status, it shows "Queued" with the estimate (or "Queued" alone when there is no estimate). Copy names the reason in plain words ("Waiting for capacity"), never another firm.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-2 | integration (Temporal test server) | Worker polls four queues; dispatched workflow and its activities run on the class queue |
| AC-3 | unit (quality rule) | DISPATCH-001 flags `start_workflow`/`task_queue=` outside the kernel |
| AC-4 | unit | Registering a workflow or loading an agent spec without a class raises |
| AC-5 | integration (scaled-down load) | Background pool saturated; an interactive retrieval starts within target |
| AC-6, AC-7, AC-8 | integration | Firm and engagement caps hold; fair hand-out across firms |
| AC-9 | integration (concurrent processes) | Admitted requests/tokens never exceed the bucket in any window |
| AC-10, AC-11 | unit + integration | Priority order; degradation ladder steps and their logs/metrics |
| AC-12 | unit (fake provider returning 429) | Bucket drained, no retry storm, caller resumes |
| AC-13, AC-14 | integration | `queued` status, reason and estimate; `capacity_timeout` after max wait |
| AC-15 | unit | Metrics emitted with identifiers only |
| AC-16 | replay | Recorded v1 histories replay; legacy-queue workflow completes |

## 19. Rollout
- **Feature flag:** none (ADR-089 flags are per firm; queues are platform-wide). The class queues are on from deploy.
- **Migration:** additive (`work_slots`, the new status values). The worker polls the class queues and, for one release, the legacy `abacus` queue, until no open workflow remains on it. Then the legacy poller is removed in a follow-up.
- **Rollback:** redeploy the previous release. Workflows started on class queues need a worker that polls them, so the previous release can't be deployed after rollout (deploy forward instead). Recorded in the runbook.

## 20. Open questions
None. Answered by the founder on 2026-10-07 (all recommendations):
- [x] **Q1: initial classes.** Retrieval started by a person is interactive and screening is time-sensitive (§6 table)? *Recommendation: yes.*
- [x] **Q2: naming clash.** ADR-069's spec field is `work_class: essential | deferrable`, but ADR-071's "work class" means one of four queues. *Recommendation: `work_class` keeps ADR-071's meaning, and ADR-069's flag becomes `essential: true|false`. Record this as a one-line ADR amending ADR-069's guidance.*
- [x] **Q3: how caps are enforced.** Options: database slot leases (`work_slots`), Temporal worker-level limits only, or Temporal task-queue fairness keys. *Recommendation: database slot leases. Worker limits can't be per firm, and Temporal fairness keys aren't generally available on our pinned server and SDK. Fair order: round-robin across waiting firms, oldest first within a firm.*
- [x] **Q4: targets and default caps.** *Recommendation:*
  - interactive schedule-to-start p95 under 2 s;
  - per-firm cap per class: interactive 20, time-sensitive 20, background 10, batch 5;
  - per-engagement cap: half the firm cap;
  - all of these are settings.
- [x] **Q5: where provider capacity lives, and the pressure thresholds.** *Recommendation:*
  - a Postgres table updated atomically, so there's no new dependency (Redis isn't allowlisted);
  - limits set to 80% of the provider's limits;
  - batch deferred below 50% remaining, and background below 25%;
  - interactive and time-sensitive always admitted while any capacity remains.
- [x] **Q6: maximum wait before `capacity_timeout`.** *Recommendation:* interactive 2 min, time-sensitive 10 min, background 6 h, batch 24 h.
- [x] **Q7: worker topology.** One process serving all four pools, or one process per class? *Recommendation:* one process locally and in CI (`--classes` defaults to all). In staging and production, a separate interactive process, so it scales independently. Deployment itself comes with TASK-014.

## 21. Future / explicitly deferred
- The budget hierarchy, metering and anomaly alerts (ADR-069), as their own spec.
- The second model route and failover (ADR-073).
- Autoscaling worker pools on queue depth.
- An operator UI for caps and pauses.
- The December load test at real volumes (ADR-075).
