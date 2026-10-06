---
id: TASK-010
title: Fake connector and the retrieval workflow
spec: SPEC-000
acceptance_criteria: [AC-9, AC-10, AC-11, AC-12, AC-19]
risk_zone: red
status: in-progress
branch: task-010-retrieval
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Connector contract and conformance suite; fake connector serving synthetic-generator trial balances; Temporal retrieval workflow running the six pipeline stages as activities; ledger snapshots; rendering a validated snapshot into an evidence version with provenance (AC-10, using TASK-009's renderer); fulfilment by rule; idempotency; replay test.

## Scope
In:
- connector contract and conformance suite;
- fake connector;
- `connections`, `sync_runs`, ledger snapshots and lines, `fulfilments`;
- `SystemContext` in `authorise`;
- the six pipeline stages as typed functions;
- the Temporal retrieval workflow, worker entry point and payload codec;
- `POST /v1/engagements/{id}/retrievals`;
- fulfilment by rule, with the request item moving to `received`;
- the replay test.

Out: real connectors, OAuth and credentials (later specs); GL detail and the roll-forward checks (only a trial balance exists in SPEC-000); screening (TASK-011); UI (TASK-012); the KMS-backed codec key (TASK-014).

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-017, ADR-037, ADR-038, ADR-040, ADR-090

## Plan
- [x] Plan approved by human (founder, 2026-10-06: "approved and proceed") — **red: founder reviews each PR line by line before merge**
- [x] Approval file `work/approvals/TASK-010.yaml` written by the agent at the founder's instruction (2026-10-06); approved by founder: paths under *Approval file text*, expires 2026-10-27
- [x] Q1–Q5: all recommendations approved. Split into **TASK-010a** (steps 1–5) and **TASK-010b** (step 6), each with its own PR.
- Red task: the agent drafts the design here; the founder edits or approves it before any code, then reviews the diff line by line (founder decision 2026-10-06).

### Design (for founder review)

**1. `SystemContext` (founder decision, TASK-009).**
- `SystemContext(tenant: TenantContext(actor_kind="system", actor_id="retrieval"), on_behalf_of: UUID, run_id: UUID)` is built only by `connections.service` from a human request that was itself authorised (`evidence.upload`). CTX-001 allows it there.
- `authorise(ctx: AuthContext | SystemContext, …)`: a system context holds the role `system` and nothing else, so the matrix decides. Today the system may do `connection.pull`, `evidence.upload`, `fulfilment.propose` and `screening.run`.
- Every audit event from the run carries the system actor. The triggering human is recorded once, on `sync_run.started` (`after.user_id`).

**2. Connector contract (`connections/connector.py`; ADR-037, ADR-040).**
- `Connector` is an ABC with `capabilities()`, `authorise_url()`, `exchange_code()`, `refresh()`, `pull(dataset, period, cursor)`, `changes_since(ts)`, `fetch_attachment(ref)` and `health()`.
- Read-only by construction: there are no write methods, and a static rule bans write HTTP verbs in connector modules.
- `pull` returns `RawPayload(bytes, media_type, source, pulled_at)` exactly as the provider sent it.
- A reusable **conformance suite** (`tests/connectors/conformance.py`) checks every connector: read-only, capabilities declared, `pull` deterministic for a cursor, errors typed.

**3. Fake connector.**
- Product code can't import tooling (ADR-101), so it serves provider-shaped JSON from `fake_connector_dir` (a setting, local/test only; refused elsewhere) at `<dir>/<connection_id>/<dataset>-<period>.json`.
- `abacus_tools.synthetic.connector_fixtures` writes those files from the synthetic generator, both for tests and for `make dev` seeding.
- It also supports injected faults: an unbalanced trial balance (AC-11), a timeout, and malformed JSON.

**4. Tables** (migration `0009`; owners in `TABLE_OWNERS`):
| Owner | Table | Notes |
|---|---|---|
| connections | `connections` | `client_entity_id`, `provider` (`fake`), `status` (`active`, `revoked`), `scopes`, `expires_at`, `created_by`; app UPDATE (`status`) only. Seeded by tooling for SPEC-000 (no client users yet). |
| connections | `sync_runs` | `connection_id`, `engagement_id`, `request_item_id`, `dataset`, `period_start`, `period_end`; `status` (`running`, `succeeded`, `failed_validation`, `failed`); `raw_storage_key`, `raw_version_id`, `raw_fingerprint`; `snapshot_id`; `failure_code`; `started_by`, `started_at`, `finished_at`. App UPDATE on status/result columns only. This doubles as the client-visible access log (ADR-040, `connection.read_log`). |
| ledger | `ledger_snapshots` | **insert-only** plus immutability trigger: `client_entity_id`, `period`, `pulled_at`, `source`, `raw_fingerprint`, `line_count`, `total_debit`, `total_credit`. Unique `(tenant, client_entity_id, period, raw_fingerprint)`, so the same pull gives the same snapshot. |
| ledger | `trial_balance_lines` | **insert-only** plus trigger: `snapshot_id`, `account_code`, `account_name`, `debit`, `credit` (`numeric(20,2)`), `source_ref`. Unique `(snapshot, account_code)`. |
| requests | `fulfilments` | `request_item_id`, `evidence_version_id → evidence_versions`, `created_by_kind` (`rule`, `human`, `agent`). Unique `(request_item, evidence_version)`. Insert-only. |

The `evidence_versions.snapshot_id → ledger_snapshots` composite FK is added here.

**5. Pipeline stages** (each a typed function, then a Temporal activity; ADR-038):
1. **extract**: `connector.pull` → `RawPayload` (the bytes stay in the activity).
2. **raw**: `evidence.api.stage_content` (write-once, encrypted, fingerprinted); records the raw key, version and fingerprint on the sync run.
3. **normalise**: read back the raw content (verified) → common ledger model (`LedgerLine` with source identifiers), with `Decimal`, never floats. Malformed → `failed`.
4. **validate**:
   - debits = credits;
   - totals match the provider's declared control totals;
   - every requested period is present;
   - no duplicate accounts;
   - amounts finite and non-negative per side.

   A failure marks the sync run `failed_validation` with a code and stops: no snapshot, no evidence (AC-11).
5. **snapshot**: insert the snapshot and lines in one unit of work (idempotent on the raw fingerprint).
6. **render**: `render_trial_balance` → `stage_content` → in one unit of work:
   - `add_version(idempotency_key=f"snapshot:{id}")`;
   - a fulfilment (`created_by_kind = rule`, `fulfilment.propose` as the system);
   - request item `open → received`;
   - sync run `succeeded`;
   - audit and outbox events (AC-10).

**6. Temporal (ADR-017, ADR-090).**
- `connections/workflows.py: RetrievalWorkflow` orchestrates only. Each stage is an activity with retries; validation failure is non-retryable.
- Payloads between activities are IDs and references, never ledger data.
- **Payload codec:** AES-256-GCM over every payload. The key comes from `temporal_payload_key` (local/test placeholder; KMS in TASK-014). A test asserts payloads at rest in Temporal are encrypted.
- Workflow ID `retrieval:<request_item_id>:<period>` with the reuse policy "allow duplicate failed only". Triggering twice while running or after success returns the existing run, so there's one snapshot (§12).
- Worker restarts resume without duplicates: every activity is idempotent (sync-run status guards, snapshot unique key, evidence idempotency key, fulfilment unique key).
- `abacus/worker/__main__.py` runs the worker. At startup it builds the key service, storage and codec (fail at boot).
- **AC-19:** a recorded history fixture (`tests/fixtures/workflows/retrieval-v1.json`) replays against current code in `make check`. Future changes use `workflow.patched`.
- import-linter: `*.workflows` may not import repositories, sessions or HTTP clients (contract in `pyproject.toml`).

**7. API.** `POST /v1/engagements/{id}/retrievals` with `{request_item_id, period_start, period_end}`:
- route action `evidence.upload`, authorised on the engagement for the human;
- finds the entity's active fake connection, else 409 `no_connection`;
- creates the sync run (`sync_run.started` audit) in one unit of work, then starts the workflow;
- returns 202 `{sync_run_id, status}`.

`GET /v1/engagements/{id}/retrievals/{sync_run_id}` (`connection.read_log`, …): **Q4**.

**7a. Static rules.**
- **CONN-001**: connector modules expose no write methods and import no HTTP client other than through `kernel` (no real HTTP in SPEC-000).
- **WF-001**: workflow modules import only `temporalio.workflow`, activity stubs and dataclasses (with the import-linter contract).

### Questions for approval
- **Q1. Split into two PRs?** TASK-010a covers the contract, fake connector, tables, `SystemContext` and the six stages as plain functions, tested end to end without Temporal. TASK-010b covers the Temporal workflow, worker, codec, trigger route, replay test and fulfilment wiring. Recommend yes: each PR stays reviewable line by line (TASK-009 alone was ~4.8k lines with tests).
- **Q2. Fake connector data via a fixtures directory written by tooling** (product can't import the synthetic generator). Recommend yes.
- **Q3. Validation scope for SPEC-000:** balance, declared control totals, period presence, duplicates and finiteness. Opening + activity = closing and GL-to-TB reconciliation wait until GL datasets exist. Recommend yes, noted against ADR-038.
- **Q4. Who can see retrieval status?** `connection.read_log` (client_admin, partner, manager) is the closest action, but staff and seniors trigger retrievals. Recommend: the trigger response and the request-item list show status, and `GET …/retrievals/{id}` uses `request_item.read`. The client-visible access log stays `connection.read_log` (later spec).
- **Q5. Payload codec key:** a platform key (not per tenant) for workflow payloads, since payloads carry only IDs. Placeholder locally, KMS in TASK-014. Recommend yes.

### Interface contract — TASK-010a (tests written independently — ADR-078)
**Imports**
- `from abacus.modules.identity.api import SystemContext, Actor, system_context, authorise, visible, Resource, Forbidden`
- `from abacus.modules.connections.api import Connector, Capabilities, ConnectorError, Unavailable, NotSupported, Period, RawPayload, FakeConnector, fixture_path, start_retrieval, StartedRun, NoConnection, connector_for, extract, store_raw, normalise_raw, validate_run, snapshot, render, run_pipeline, RunFailed, RunResult`
- `from abacus.modules.ledger.api import normalise, validate, NormaliseError, NormalisedTrialBalance, LedgerLine, record_snapshot, SnapshotRef, Unvalidated, trial_balance_for`
- `from abacus.modules.requests.api import fulfil_by_rule, FulfilmentRef`
- `from abacus_tools.synthetic.connector_fixtures import write_trial_balance, write_fault, write_raw, trial_balance_document`

**SystemContext**
- `system_context(auth_ctx, run_id)` → `SystemContext(tenant=TenantContext(t, "system", "run:<run_id>"), on_behalf_of=user_id, run_id)`.
- In `authorise`, the system holds only the role `system`. Today it is allowed `connection.pull`, `evidence.upload`, `fulfilment.propose`, `screening.run`, `support_match.run` and `connection.pull`, and everything else is `Forbidden` at layer `role`. Tenancy still applies.
- `visible(system_ctx, read_action, col)` → `true()` if the matrix gives `system: allow`, else `false()`.
- Denial and allow logs carry `system_run_id` and `on_behalf_of` for the system, and `user_id` for humans.
- CTX-001 flags `SystemContext(...)` outside `identity/service.py`.

**Connector contract and fake connector**
- `Connector` is abstract and every method in the contract is abstract. The conformance checks that any connector must pass:
  - `capabilities()` returns `Capabilities`;
  - `pull` of a declared dataset returns `RawPayload` with bytes identical to the provider's response, and is deterministic for the same period and cursor;
  - an undeclared dataset → `NotSupported`;
  - OAuth methods raise `NotSupported` when `capabilities().oauth` is False;
  - no method is write-shaped (CONN-001).

  Write the conformance checks as a reusable suite, `tests/connectors/conformance.py`, parametrised over connector factories, and run it on `FakeConnector`.
- `FakeConnector(connection_id, directory)`:
  - reads `fixture_path(dir, connection_id, "trial_balance", period)`;
  - a missing file → `ConnectorError("no_data")`;
  - `{"fault": "unavailable"}` → `Unavailable("provider_unavailable")`;
  - malformed bytes are returned as they are;
  - `health()` is True iff the directory exists.
- Settings: `fake_connector_dir` set outside local/test → validation error.

**Ledger**
- `normalise(bytes)` → `NormalisedTrialBalance(period_start, period_end, lines, declared_debit, declared_credit)`, with amounts as `Decimal` quantised to cents.
- It raises `NormaliseError("malformed_payload")` for: invalid JSON or UTF-8; a non-object; `dataset` ≠ `trial_balance`; missing fields; non-string amounts (JSON numbers); text that is empty, over 200 characters or contains control characters; more than 50,000 lines.
- It raises `NormaliseError("invalid_amount")` for: unparseable, non-finite or negative amounts; more than 2 decimal places; ≥ 1e15.
- `validate(tb, *, period_start, period_end)` checks in this order: `empty`, `period_mismatch`, `duplicate_account`, `control_totals_mismatch` (computed ≠ declared), `unbalanced`. It returns `None` when all pass.
- `record_snapshot(tx, …)`:
  - re-validates (`Unvalidated`);
  - inserts the snapshot and lines and records `ledger_snapshot.created`;
  - the same `(entity, period, raw_fingerprint)` → `SnapshotRef(existing, created=False)` with no new rows and no audit event.
- `trial_balance_for(tenant, snapshot_id, entity_name=…)` → `evidence.api.TrialBalance` with lines sorted by code and `source_fingerprint` = raw fingerprint.

**Requests.** `fulfil_by_rule(tx, ctx, request_item_id=…, evidence_version_id=…)`:
- authorises `fulfilment.propose` for `ctx` on the item's engagement (a human staff member → `Forbidden`; the system → allowed);
- inserts `fulfilments(created_by_kind='rule', created_by_id=<tx actor id>)` once per (item, version), with audit event `fulfilment.created`;
- moves the item `open → received` (audit event `request_item.received`), and only from `open`;
- a repeat → `FulfilmentRef(id=None, received=False)`.

**Pipeline** (seed as superuser: firm, user, membership, client, entity, engagement, member, request list and items, `connections(provider='fake')`; fixtures via `write_trial_balance`; storage as in TASK-009 tests)
- `start_retrieval(ctx, engagement_id=…, request_item_id=…, period=…)`:
  - needs `evidence.upload` (reviewer → `Forbidden`, nothing written);
  - no active, unexpired connection for the entity → `NoConnection`;
  - inserts `sync_runs(status='running', started_by=<user id>)` with audit event `sync_run.started` (`after.user_id`, `after.request_item_id`);
  - a request item from another engagement → database error, nothing written.
- **AC-9 and AC-10** via `run_pipeline(system, run_id)`:
  - the raw payload is stored in the evidence store under its fingerprint, encrypted;
  - the sync run records `raw_*`, then `snapshot_id`, then `status='succeeded'` with `finished_at`;
  - one snapshot with the right line count and totals;
  - one evidence version: method `retrieved`, `pulled_at`, period, entity, `snapshot_id`, fingerprint, `.xlsx` media type;
  - one fulfilment `rule`; the item is `received`;
  - audit events in order: `sync_run.started`, `sync_run.raw_stored`, `ledger_snapshot.created`, `sync_run.snapshot_linked`, `evidence_item.created`, `evidence_version.created`, `fulfilment.created`, `request_item.received`, `sync_run.succeeded`;
  - outbox: `evidence_version.created`.
- **AC-11:** an unbalanced fixture (or a declared-totals mismatch) → `RunFailed("failed_validation", "unbalanced"|"control_totals_mismatch")`. The run is `failed_validation` with `failure_code`. There's no snapshot, no evidence version and no fulfilment; the item stays `open`; and there's a `sync_run.failed` audit event.
- **Failures:**
  - a malformed payload → `RunFailed("failed", "malformed_payload")`;
  - a missing fixture → `RunFailed("failed", "no_data")`;
  - a fault → `RunFailed("failed", "provider_unavailable")` from `run_pipeline` (`extract` alone raises `Unavailable`);
  - a revoked connection → `RunFailed("failed", "connection_inactive")`.
- **Idempotency (§12):**
  - running any stage again after success returns the same result (`render` → the same version ID; `snapshot` → the same snapshot ID; `store_raw` → the same object);
  - a second `start_retrieval` plus `run_pipeline` for the same item and period → the same snapshot and version, and still one fulfilment;
  - stages on a failed run raise `RunFailed`;
  - a stage given another run's ID than its system context's → `NotFound`.
- **Database (migration 0009):**
  - the new tables have forced RLS and the owners in `TABLE_OWNERS`;
  - `ledger_snapshots` and `trial_balance_lines` are insert-only, and as superuser UPDATE, DELETE and TRUNCATE are rejected by the trigger;
  - CHECKs: snapshot `total_debit = total_credit`; amounts ≥ 0; `sync_runs` finished ⇔ not running; `failure_code` ⇔ failed;
  - composite FKs: a sync run's item must be in its engagement; snapshot and fulfilment links stay within the tenant; `evidence_versions.snapshot_id` → `ledger_snapshots`;
  - grants: the app can't INSERT `connections` and may UPDATE only its `status`; it may UPDATE only the result columns of `sync_runs`;
  - downgrading 0009 raises while snapshots exist.

**Static rules**
- **CONN-001** (in `connections/connector.py`, `fake.py` and `connectors/*`): importing `httpx`, `requests`, `aiohttp`, `urllib3`, `urllib.request` or `http.client`, or defining a function whose name (without leading underscores) starts with `create`, `update`, `delete`, `write`, `post`, `put`, `patch`, `upload` or `send`.
- **BOUND-002** now allows:
  - `ledger` → identity, evidence;
  - `connections` → identity, engagements, organisations, ledger, evidence, requests.
- **LIST-001** exempts `ledger/repository.py:lines_of`.

### Approval file text
```yaml
task: TASK-010
approved_by: founder
expires: 2026-10-27
paths:
  - .claude/hooks/_protected.py
  - .github/CODEOWNERS
  - docs/architecture/protected-paths.md
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/src/abacus/kernel/**
  - backend/src/abacus/modules/identity/**
  - backend/src/abacus/modules/connections/**
  - backend/src/abacus/modules/ledger/**
  - backend/src/abacus/modules/evidence/**
  - backend/src/abacus/modules/requests/**
  - backend/src/abacus/api/**
  - backend/src/abacus/worker/**
  - backend/src/abacus_tools/quality/schema_check.py
  - backend/src/abacus_tools/quality/banned_patterns.py
  - backend/tests/unit/quality/test_banned_patterns.py
  - packages/api-client/**
reason: TASK-010 — connector, ledger snapshots, fulfilments, retrieval pipeline and workflow
```

### Steps (if Q1 is approved, TASK-010a is steps 1–5)
1. Approval file; protect `modules/connections/**`, `modules/ledger/**`, `abacus/worker/**`.
2. `SystemContext` in identity/authz; migration `0009`; `schema_check` maps, triggers and owners.
3. Connector contract; fake connector; `abacus_tools` fixtures.
4. Ledger normalise, validate and snapshot; requests fulfilments; connections `sync_runs` and service.
5. The six stages as functions; contract → independent tests; reviews; PR.
6. (TASK-010b) Codec, workflow and activities, worker, trigger route, replay fixture, WF-001 and the import contract; contract → tests; reviews; PR.

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
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-06` — Design drafted (§1–7, Q1–Q5) for founder review.
- `2026-10-06` — Approved with all recommendations (split into 010a/010b); approval file written at the founder's instruction. Starting TASK-010a.
- `2026-10-06` — 010a implemented. Smoke-tested end to end:
  - AC-9/10 happy path;
  - idempotent re-render and re-retrieval (one snapshot, one version, one fulfilment);
  - AC-11 unbalanced → `failed_validation`, item stays open.

  Migration 0009 (my own, unmerged, never applied) was edited in place to add `sync_runs.raw_size_bytes` and `raw_pulled_at`; no new migration. 010a contract written.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
- From TASK-009 (founder, 2026-10-06): add a `SystemContext` that `authorise` accepts (`evidence.upload`, `connection.pull`, `screening.run`).
- Evidence: stage content with `evidence.api.stage_content` **before** the unit of work, then `add_version(..., idempotency_key=<workflow/activity id>)`. A repeat returns `created=False` and records nothing, so record your own event or skip. Raw payloads use `stage_content`/`read_content` too.
- Add the `evidence_versions.snapshot_id` composite FK, and `ledger: {identity, engagements, evidence}` in `MODULE_DEPENDENCIES`.
- Call `key_service()` and the storage target at worker startup (fail at boot).
-

## Questions for the human
-

## Handoff
- **Current state:** TASK-010a implemented and committed on `task-010-retrieval` (WIP). Contract written. The independent test author and two reviews are next.
- **Exact next step:** Collect tests and reviews; fix; `make check`; PR for TASK-010a (red: founder line-by-line). Then TASK-010b (step 6).
- **Uncommitted or partial work:** none.
- **Known failing checks:** older tests that seed `request_items` may need nothing new; `engagements` tests may check `EngagementRef` fields.
- **Open issues:** branch protection off.
