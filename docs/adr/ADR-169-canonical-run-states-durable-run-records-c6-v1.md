---
id: ADR-169
title: Canonical agent run states with the legacy status map; decision-relevant run records persisted at completion under engagement retention; the C6 v1 stub shape
status: accepted
date: 2026-10-24
deciders: notanaskhan, ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.
> - **Accepted 2026-10-24.** Q-02-T41 (run records), Q-02-T45 (the C6 v1 stub) and P-10-T14 (the state migration) may proceed once this reads `accepted` on `origin/main`.

## Status and acceptance

Drafted by Q-02-T34 as plan proposal **P-47** (AG-03; conflict C-12). The plan's due date for acceptance is Fri Feb 19, 2027 (Q-02 table 0.1; P-10's "Must be accepted first" row; the plan's alias "ADR-147" is void, because ADR-147 is the role catalogue: numbers come only from `docs/adr/backlog.md`).

**Acceptance record:**
- 2026-10-24: ayushkbhatia accepted, in the build session. Under `docs/plan/AMENDMENT-solo.md` (one builder; no approvals to wait for), that is the deciders' acceptance; notanaskhan's separate sign-off is not required. No counsel input is needed: retention follows ADR-033 and the published floors.

## Context

- **States.** `agent_runs.status` has four codes (migration 0010: `running`, `completed`, `escalated`, `failed`), plus `queued_reason` for a run waiting on a work slot (0013). The product's status vocabulary (blueprint §3.3.1; `docs/product/status-vocabulary.yaml`, object `agent_run`) has fourteen: eleven stored and three outcomes derived from people's decisions. C6 v0 (`docs/contracts/agent-runs.md` §4) already maps the four codes to the canonical words at read time. P-10's runtime (plans, steps, questions, decisions) needs the canonical states stored, with a reason and what a blocked run waits on.
- **Run records (C-12).** ADR-032 keeps raw model traces about 30 days and says "decision-relevant agent runs share the engagement's retention", without saying what is kept. Today nothing outlives the trace: after about 30 days a reviewer can no longer show which prompt version, model, route, region and sources produced the proposal a person accepted. Audit documentation must be retained for at least five years after report release (Q-02 §7.3), and the archive (A-07, ADR-159) packages run records at lock. Q-02 AC-44 needs one durable, insert-only record per completed specialist run.
- **C6 v1.** G-02 and A-01 read run summaries with a record fingerprint from S11–S12 (Q-02 OQ-3); P-09 brings v1.1 and P-10 v2. The v1 shape must extend v0 without breaking it.

## Decision

### 1. Canonical run states

`agent_runs` gains `state`, `state_reason` and `blocked_on`. Stored states, in their forward order (the state machine of chapter 05 §5.3.6):

| State | Terminal | Meaning |
|---|---|---|
| `queued` | no | accepted, waiting for a work slot or a dependency (`queued_reason`) |
| `planning` | no | the run is building its plan |
| `awaiting_plan_approval` | no | the plan declares writes and needs a person's approval |
| `dispatched` | no | the plan is approved or needs none; steps are being handed out |
| `running` | no | at least one step is dispatched or running |
| `needs_input` | no | a question is open and no step can run (`state_reason = escalated` for a specialist escalation) |
| `blocked_on_decision` | no | only branches waiting on a person's decision remain (`blocked_on` names the decision, role and person) |
| `waiting_on_inputs` | no | only branches waiting on client or system inputs remain |
| `succeeded` | yes | every step is terminal and the run produced its outputs ("Ready for review") |
| `failed` | yes | a required step failed with no remaining branch |
| `cancelled` | yes | a person stopped it, or the plan was cancelled |

Derived, never stored: `approved`, `partially_approved`, `rejected`, computed from the decisions on the run's proposals once the last one is decided. `failed` and `cancelled` are reachable from every non-terminal state. A forward-only trigger (the 0010 pattern, generalised) refuses any other move. The aggregate rule for a run with steps is chapter 05's: `running` if any step is dispatched or running, else the first of `needs_input`, `blocked_on_decision`, `waiting_on_inputs`; `succeeded` or `failed` once every step is terminal.

### 2. The legacy map, and the migration

| `agent_runs.status` (0010) | `state` | `state_reason` |
|---|---|---|
| `running` | `running`, or `queued` while `queued_reason` is set | the `queued_reason` code when queued |
| `completed` | `succeeded` | — |
| `escalated` | `needs_input` | `escalated` |
| `failed` | `failed` | — |

The migration is additive: `state` is added and back-filled from the map in the same migration; `status` stays as a **generated compatibility column** (`running` ⇐ any non-terminal state; `completed` ⇐ `succeeded`; `escalated` ⇐ `needs_input` with reason `escalated`; `failed` ⇐ `failed` or `cancelled`) until every specialist workflow writes `state`. Each specialist moves behind `workflow.patched(...)` with a recorded replay history (ADR-090). `status` and its CHECK are dropped only after the last reader is gone. The status vocabulary already carries the `agent_run` codes and the retired `agent_run.completed` and `agent_run.escalated`; the codegen keeps the enums and the database CHECK in step.

### 3. Durable run records

A **run record** is the decision-relevant facts of one run, written once when the run reaches a terminal state, kept for the engagement's retention, and never updated. It holds identifiers, versions and fingerprints only: no prompt text, no model text, no client content.

- **Which runs.** Every run of a specialist capability (screener, upload reviewer, matcher, guidance drafter; later P-10's capabilities) that reaches `succeeded`, `failed` or `cancelled`. All four are decision-relevant: each produces outputs a person accepts, edits or rejects. Shadow-stage runs get a record too, marked by `stage`, because the shadow report is the evidence for promoting an agent (SPEC-036). Firm-level runs without an engagement (template guidance drafts) are kept under the firm's default for the record type until P-14's record-class registry names their anchor.
- **When.** At completion, by a `persist_run_record` activity in the run's own workflow, after the terminal state is written. Repeat-safe: one record per run (`run_id` primary key). The unit of work writes the `agent_run_record.persisted` audit event (actor: system), whose `after` reference carries `record_sha256`, so the record is covered by the per-tenant audit hash chain (ADR-159).
- **Fields and retention.** Every field shares the record's retention: record class `agent_run_records`, anchored on the engagement's `report_release` (audit and assurance) or `filing_date` (tax), firm default 7 years, never below the published floor, held by any legal hold covering the engagement (ADR-033, `kernel.holds`), stored in the database (and packaged into the sealed archive at lock, A-07).

| Field | Content | Classification | Retention |
|---|---|---|---|
| `run_id` | the run (primary key; references `agent_runs`) | internal | record |
| `tenant_id` | the firm (forced RLS) | internal | record |
| `engagement_id`, `work_item_id` | where the run worked (work item optional) | internal | record |
| `capability` | the specialist capability code | internal | record |
| `spec_version` | the agent spec version that ran | internal | record |
| `stage` | `shadow` or `live` at the time of the run | internal | record |
| `prompt_ref`, `prompt_sha256` | the registered prompt id and version, and the SHA-256 of its text | internal | record |
| `model` | the model identifier the gateway called | internal | record |
| `route`, `region` | the approved route and the region it ran in | internal | record |
| `terms_version` | the provider-terms register version that allowed the call (null for synthetic firms) | internal | record |
| `boundary_basis` | why the data boundary allowed it (`synthetic`, `opted_in`) | internal | record |
| `input_hashes` | SHA-256 of each input the run was given, by input kind | internal | record |
| `records_read` | identifiers of the records read (type and id), never their content | internal | record |
| `citations` | each citation's locator (document, page, region or cell) and the SHA-256 of the quoted words, never the quote | internal | record |
| `outcome` | the terminal state and the counts of outputs by kind | internal | record |
| `initiator_user_id` | the person the run acted for (ADR-025) | internal | record |
| `started_at`, `completed_at` | business-clock instants | internal | record |
| `record_sha256` | SHA-256 of the canonical JSON of every field above (sorted keys, UTC instants) | internal | record |

The raw trace (gateway attempts, model text, step detail) keeps ADR-032's ~30 days and is never needed to read a record. A record past its retention, with no hold, is destroyed with its engagement's other records (Q-05), and the destruction is audited; nothing else deletes one.

### 4. The C6 v1 stub shape

C6 v1 is additive to v0's live routes (`docs/contracts/agent-runs.md`), on the same `agent_run.read` action (engagement members through the engagement; `security_admin` reads metadata only, DEC-87; walls answer 404; agent and client principals denied):

- `GET /v1/engagements/{engagement_id}/agent-runs` and `GET /v1/agent-runs/{run_id}`: the run summary gains `state` (canonical, stored), `state_reason`, `outcome` (the derived outcome or null), `stage`, `record_sha256` and `record_persisted_at` (null until persisted).
- `GET /v1/agent-runs/{run_id}/record`: the run record's fields of §3, as stored, for consumers that verify or package it (A-07, G-02). Content-free by construction, so it carries no Restricted field.
- v0's `state` words stay valid: the four v0 codes are a subset of the canonical ones.

The stub (Q-02-T45) ships these models with seed-derived fixtures behind its contract flag before the routes go live.

## Options considered

### Option A: a separate, insert-only run record written at completion, under engagement retention — chosen
- Pros: answers "what produced this proposal" for as long as the audit documentation is kept, without keeping model text; small and content-free, so it adds no Restricted data; one hash per run joins the audit chain; the trace keeps its short retention.
- Cons: one more table and activity per specialist workflow; patched workflows and replay histories for each.

### Option B: keep raw traces for the engagement's retention
- Pros: no new table; everything is kept.
- Cons: model text is Confidential client-derived content, so keeping it for seven years widens what a breach exposes and what retention and holds must cover; storage cost grows with every attempt; contradicts ADR-032's ~30 days.
- Why rejected: it keeps far more than the decision needs.

### Option C: carry the facts in audit events only
- Pros: already chained and retained.
- Cons: audit `before`/`after` references are identifier-only by design (`kernel.uow.Ref`); citations and input hashes do not fit, and the audit trail is not a query surface for run facts.
- Why rejected: it would stretch the audit grammar; the audit event carries the record's fingerprint instead.

### Option D: store the derived outcomes (`approved`, `partially_approved`, `rejected`) as states
- Pros: one column answers the badge.
- Cons: the outcome changes with each later decision or Undo, so a stored outcome goes stale; a forward-only state machine cannot move back.
- Why rejected: derived at read time from decisions, as the vocabulary marks them.

## Consequences

**Positive**
- A reviewer, an inspector or the archive can show, years later, which spec, prompt, model, route, region, terms and sources produced any accepted proposal.
- The run-state words on every screen come from one stored column, with no read-time map.
- C6 v1 consumers get a fingerprint they can verify against the chained audit event.

**Negative / costs accepted**
- Every specialist workflow is patched twice (state writes, record persistence), each with a recorded replay history.
- Records follow destruction rules and holds like other engagement records; Q-05's destruction batch must include them.
- The compatibility `status` column lives until the last specialist moves.

**Follow-up work created**
- Q-02-T41: `agent_run_records` (migration, insert-only, schema-check registration, record class), `persist_run_record` in the four specialists, AC-44.
- Q-02-T45: the C6 v1 stub (models, fixtures, consumer tests).
- P-10-T14: the `state` migration, the trigger, the generated `status`, the specialist moves.
- P-14 (retention): register the `agent_run_records` record class and the firm-level anchor.
- A-07: package records at archive lock.

## Enforcement
- `agent_run_records` is registered insert-only in the agents module registry and checked by `abacus_tools.quality.schema_check` (no app UPDATE or DELETE).
- Q-02 AC-44 (Q-02-T41, with the independent AC tests of Q-02-T46): a run completed 90 days earlier still yields its record after its trace is pruned, and the record's fields equal the run's.
- Replay histories for every patched workflow (ADR-090); a schedule change without a patch is non-determinism.
- The status vocabulary codegen holds the database CHECK, the OpenAPI enum and `status.ts` to the `agent_run` codes; derived codes are never stored (`test_t09_derived_codes_are_never_stored`).
- The audit chain verifier recomputes `record_sha256` for records it meets (ADR-159).

## Guidance for agents

**Do**
```python
# at completion, inside the run's workflow, after the terminal state is written
if workflow.patched("run_record_v1"):
    await workflow.execute_activity("agents.persist_run_record", RunRecordInput(run_id), ...)
```

**Don't**
```python
# keeping model text or quotes in a record, or updating one
record["model_text"] = output.text
await session.execute(text("UPDATE agent_run_records SET outcome = :o"), ...)
```

## Revisit when
- P-10's runtime adds step-level records that a reviewer must keep (then a record may reference step summaries, still content-free).
- A firm's retention policy or a regulator requires the model text itself to be kept (then counsel, and a new ADR).

## Related
- ADRs: ADR-005, ADR-007, ADR-016, ADR-025, ADR-032 (amended by this ADR for what "decision-relevant agent runs" keeps), ADR-033, ADR-062, ADR-063, ADR-090, ADR-159 (P-43), ADR-167.
- Plan: chapter 09 P-47 row; chapter 05 §5.3.6; Q-02 §3.12 (AC-44), §4.2, §7.3, table 0.1; P-10 "Must be accepted first"; C-12.
- Contracts: `docs/contracts/agent-runs.md` (C6 v0).
