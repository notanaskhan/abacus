---
id: TASK-019
title: Review queues and review decisions
spec: SPEC-004
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14]
risk_zone: red
status: in-progress
branch: task-019-review-queues
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
Implement SPEC-004.
- **The queue:** evidence awaiting a human's judgement is queued per engagement, and a reviewer takes it.
- **The decision:** the reviewer records a review decision (accept, reject or send back). Reject and send back require a reason code. Decisions are human-only (ADR-005), insert-only and audited.
- **For the Learning layer:** decisions, reason codes and corrections of the agent's proposal are stored.

## Scope
All of SPEC-004 (AC-1 to AC-14), once approved.

Excluded:
- the learning loop (ADR-068);
- follow-ups on send-back (increment 8);
- suggestions beyond screening results;
- reopening accepted items;
- sign-off workflows;
- firm settings.

SPEC-004 approved by the founder on 2026-10-07 (all recommendations, Q1–Q8). Next: the design, for founder review (red: authorisation and human decisions).

## Context to load
- **Spec:** `docs/specs/SPEC-004-review-queues.md`
- **ADRs:** ADR-005, ADR-054, ADR-004, ADR-007, ADR-020, ADR-026, ADR-027, ADR-031, ADR-061, ADR-068, ADR-102
- **Code:**
  - `backend/src/abacus/modules/evidence/` (versions, routes)
  - `backend/src/abacus/modules/requests/` (item statuses)
  - `backend/src/abacus/modules/agents/` (screening results, the handoff)
  - `backend/src/abacus/modules/identity/authz/`
  - `docs/architecture/permission-matrix.yaml`
- **Reference:** `docs/architecture/reference/` (backend module, tenancy and authz, unit of work); the `backend-module` skill

## Plan
- [x] Plan approved by human (founder, 2026-10-07: D1–D5 as recommended)
- Approved by founder: paths in the design's "Protected paths" list (local approval file `work/approvals/TASK-019.yaml`, written at the founder's instruction).

### Design (for founder review)

**§1 Ownership and module boundaries (Q4).**
- `evidence` owns `review_decisions`, `review_assignments` and `review_reason_codes`, and serves every review route.
- The queue needs three modules' facts:
  - evidence versions (evidence);
  - which request item each version fulfils (requests, `fulfilments`);
  - the screener's proposal (agents, `screening_results`).
- Modules never read each other's tables (ADR-008), so the queue is composed through APIs:
  - **requests** (`requests.api`, which evidence may import; requests imports nothing of evidence) gains:
    - `item_versions(tenant, engagement_id) -> [(request_item_id, evidence_version_id, fulfilled_at)]`;
    - `move_after_review(tx, request_item_id, to_status)`, which applies only the transitions allowed in SPEC-004 §6.
  - **agents** already imports evidence, so evidence can't import agents. Agents registers a proposal lookup with evidence at import, `register_proposal_source(proposals_for)`, the same inversion as walls (TASK-016) and work classes (TASK-018). `proposals_for(tenant, version_ids) -> {version_id: Proposal(screening_result_id, action, confidence, rationale, citations, unverified)}`, using the latest result per version. Unregistered, the queue shows no proposals, and a decision can't know whether it corrects one: `decide` then refuses with 503 (fail closed, so no correction flag is guessed).

**§2 Data (migration 0015).**
- **`review_decisions`:** tenant-scoped, forced RLS, insert-only, with immutability triggers (ADR-004).
  - Columns: `id`, `tenant_id`, `engagement_id`, `evidence_version_id`, `request_item_id`, `decision` (accept, reject, send_back), `reason_code`, `note` (≤ 2,000 characters, classified confidential), `screening_result_id` (nullable), `corrects_proposal`, `actor_kind`, `actor_id`, `created_at`.
  - CHECKs:
    - `actor_kind = 'human'` (ADR-005, the database layer);
    - a reason code is required for `reject` and `send_back`, and absent for `accept`.
  - One decision per version: UNIQUE (`tenant_id`, `evidence_version_id`).
  - Foreign keys to evidence versions, request items and screening results, all within the tenant.
- **`review_assignments`:** tenant-scoped, forced RLS.
  - Columns: `(tenant_id, evidence_version_id)` as the PK, `engagement_id`, `assignee_user_id` (nullable: released), `assigned_by`, `assigned_at`.
  - The app may insert and update `assignee_user_id`, `assigned_by` and `assigned_at`; it may not delete.
- **`review_reason_codes`:** a platform catalogue (Q1) with `code`, `applies_to` (reject, send_back), `label`, `description`, `active`.
  - Seeded with: `wrong_period`, `wrong_entity`, `incomplete`, `illegible`, `does_not_agree`, `unsigned`, `other` (`other` requires a note).
  - It has no tenant, so the app gets no privileges on it, the same pattern as the work-slot ledger (TASK-018 D3).
  - The app reads it through a SECURITY DEFINER function, `review_reason_codes_list(applies_to)`.
  - A SECURITY DEFINER `BEFORE INSERT` trigger on `review_decisions` refuses a code that is unknown, retired, or doesn't apply to the decision, and refuses `other` without a note. Both are added to `DEFINER_FUNCTIONS`.
- **`request_items.status`:** gains `accepted` (Q2).
- `schema_check` maps: `TABLE_OWNERS`, the insert-only and immutable lists, and the column grants.

**§3 Authorisation (Q7, Q8; matrix changes are protected).**
New matrix actions:
| Action | Allowed | Notes |
|---|---|---|
| `review.read` | everyone who has `request_item.read` today, minus client roles | a read action, so `visible()` and walls apply |
| `review.take` | `engagement_partner`, `manager`; `senior` under `firm_setting(seniors_can_accept)` | the same people who can decide |
| `review.assign` | `engagement_partner`, `manager` | |
- Agents and system are denied all three.
- Deciding uses the existing actions, unchanged: `evidence.accept` for accept, `evidence.reject` for reject and send back.
- `decide` and `take` accept only an `AuthContext`, so an agent or system context fails type-checking. A runtime `isinstance` check and the database CHECK back that up. A new lint rule, REVIEW-001, flags a call to `decide` from any `agents`, `connections` or worker code.
- Single-engagement routes `authorise` against `engagement.resource()` (so walls give 404). The queue's lists apply `visible()`.

**§4 The queue (AC-1 to AC-3; Q3).**
- **Contents:** for one engagement, the newest fulfilled version per request item (by `fulfilled_at`, then `version_no`) that has no decision.
- **Each entry:** the item (description and audit area), a version summary (provenance), the proposal (if any) and the assignee.
- **Order:** proposals of `needs_revision` first, then ascending confidence (no proposal sorts last within its group), then oldest.
- The queue is computed in the service, not stored. Hundreds of items per engagement is fine (spec §16).

**§5 Taking and assigning (AC-4, AC-5).**
- **Take:** an upsert. If someone else holds the item, it returns 409 `already_taken`. Audited `review.taken`.
- **Release:** allowed for the assignee, or a partner or manager (`review.assign`). Audited `review.released`.
- **Assign:** `review.assign` only. The assignee must be an engagement member who could decide. Audited `review.assigned`.
- Taking is advisory (Q3). Deciding doesn't need it, and the decision records who decided.

**§6 Deciding (AC-6 to AC-13).**
All in one unit of work:
1. Lock the version's engagement (`lock_ref`) and `authorise` (`evidence.accept` or `evidence.reject`).
2. Check the version is the item's newest (otherwise 409 `superseded`) and undecided (otherwise 409 `already_decided`; the UNIQUE constraint backs up races).
3. Fetch the proposal and set `corrects_proposal`.
4. Insert the decision.
5. Move the item (`requests.move_after_review`):
   - accept → `accepted`;
   - reject → `received` if the item has another undecided fulfilled version, else `open`;
   - send back → `needs_revision`.
6. Clear the assignment.
7. Record `review_decision.created`. The audit carries the identifiers (version, item, screening result) as refs. The decision, reason code and correction flag are on the row, never in the audit text. The note is never logged.

Responses:
- 201 with the decision.
- 422 for an unknown or retired reason code, a missing one, or `other` without a note.
- 404 for a walled person.
- 403 for anyone without the right. Seniors are refused until firm settings exist (Q8).

**§7 Routes (evidence module).**
| Route | Action |
|---|---|
| `GET /v1/engagements/{id}/review-queue` | `review.read` |
| `POST …/review-queue/{version_id}/take` | `review.take` |
| `POST …/review-queue/{version_id}/release` | `review.take`; another's item needs `review.assign` |
| `POST …/review-queue/{version_id}/assign` | `review.assign` |
| `POST /v1/engagements/{id}/evidence-versions/{version_id}/decision` | `evidence.accept` or `evidence.reject`, by decision |
| `GET /v1/engagements/{id}/review-reason-codes` | `review.read` |
- **Deviation:** the reason-code catalogue moves under the engagement path. A firm-level `review.read` has no engagement role to grant it. Recorded in the decisions table.
- The API client is regenerated.

**§8 Observability.**
- **Logs:** `review.decided` (decision, reason code, correction flag, IDs) and `review.taken`.
- **Metric:** counter `abacus.review.decisions`, with `outcome` (accept, reject or send_back) and `reason` (the reason code, or "agreement" or "correction"). Both attributes are on the allowlist.

**§9 SPA (Q6).** A minimal "Review" screen per engagement:
- the queue list, with the proposal's action and confidence and the assignee;
- take and release;
- accept, reject and send back, with a reason-code select and an optional note.

Errors show the API's messages. Full item detail is increment 6.

**Protected paths (approval file):**
- `backend/src/abacus/modules/evidence/**`
- `backend/src/abacus/modules/agents/**`
- `backend/src/abacus/modules/identity/**` (only if the `_matrix.py` regeneration counts)
- `backend/src/abacus/api/**`
- `backend/migrations/**`
- `docs/architecture/permission-matrix.yaml`
- `backend/src/abacus_tools/quality/schema_check.py`
- `backend/src/abacus_tools/quality/banned_patterns.py` and its test (REVIEW-001)
- `packages/api-client/**`
- `.claude/skills/**`

`requests` and `apps/web` aren't protected.

### Questions for approval
- **D1. Proposals reach evidence through a registration, the same inversion as walls?** *Recommendation: yes.* Agents already depends on evidence. If the registration is missing, a decision fails closed with 503, so no correction flag is ever guessed.
- **D2. The reason-code catalogue is a platform table reached only through a SECURITY DEFINER list function, with a SECURITY DEFINER trigger validating codes on insert?** *Recommendation: yes.* It follows the TASK-018 D3 pattern and keeps the app's privileges on global tables at zero.
- **D3. The catalogue route is `GET /v1/engagements/{id}/review-reason-codes`, not the spec's firm-level path?** *Recommendation: yes.* A firm-level `review.read` has no engagement role to grant it.
- **D4. New lint rule REVIEW-001: `decide` is never called from agents, connections or the worker?** *Recommendation: yes.* It's a fourth layer for ADR-005, alongside the service type, the matrix and the database CHECK.
- **D5. Write the approval file for the protected paths above?** *Recommendation: yes.*

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
- `2026-10-07` — Rebased onto main after 018b (#28) and 018c (#29), with pin updates (the 201 routes and the definer functions). The founder waived the red-zone line-by-line review: "merge 019 too when green, skip my review". Independent tests are still deferred.
- `2026-10-07` — Reviews: security (H1 release across engagements, H2 ADR-005 sidesteps, H3 races, M1–M3, L1–L4) and architecture (B1 reject stranding, B2 BOUND-002 test, B4 pool starvation, M1–M13, nits).
  - **Fixed:**
    - decisions read and lock inside their own unit of work, through `requests.review_targets` (items locked FOR UPDATE; `fulfil_by_rule` locks the item too);
    - reject → `open`, and every item the version fulfils moves;
    - `seen_proposal` → 409 `proposal_changed`;
    - `decide` only while `serving_request()`;
    - the database binds `actor_kind`/`actor_id` to the session;
    - REVIEW-001 is now an allowlist;
    - an atomic take;
    - assignments are scoped to the engagement;
    - validation runs after `authorise`;
    - `DomainInvalid` (422 with a fixed code);
    - per-route bodies;
    - blank notes are refused;
    - IntegrityError is mapped by constraint name;
    - the newest version per item is chosen by fulfilment;
    - one queue read;
    - typed citations;
    - the SPA (provenance, citations, unverified points, owner-aware take and release, refresh on error, catalogue errors, the note requirement, aria labels, the router link);
    - ADR-106;
    - SPEC-004 §8 amended;
    - READMEs.
  - A throwaway check passed against Postgres: concurrent takes, refusal outside a request, the actor bound to the session, and a cross-engagement release answering 404.
  - **Open:** N3 (the SPA shows decision controls to staff, who get a 403).
- `2026-10-07` — Founder approved the recommendations: `assign` checks `identity.could` (M2); the SPA asks for confirmation before a decision (N4).
- `2026-10-07` — SPEC-004 approved and merged (PR #27). Design approved (D1–D5). Implemented:
  - migration 0015;
  - the matrix actions `review.read`, `review.take` and `review.assign`;
  - requests `fulfilled_versions` and `move_after_review`;
  - evidence's review service, routes and proposal registration;
  - agents `proposals_for` and `proposal_of`;
  - REVIEW-001;
  - the schema_check maps;
  - the SPA Review screen;
  - the API client;
  - the docs.

  Static gates pass, and `schema_check` passes. A throwaway end-to-end check passed against Postgres (queue, take and conflict, reason-code validation, a 403 for staff, reject, accept, item statuses, audit events, and the database refusing a non-human actor); it wasn't committed. Independent tests are deferred (founder, 2026-10-07: "skip test authors for now").
- `2026-10-07` — Created with SPEC-004 (draft) for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Three decision routes (`…/decision/accept`, `/reject`, `/send-back`), not one | Each route declares exactly one matrix action, and accept and reject differ | No (spec §8 note) |
| A sent-back (`needs_revision`) item takes new evidence and becomes `received` | Otherwise send back is a dead end: retrieval refused anything but `open`/`received` | No |
| The assignee of `assign` must be someone who could decide now (`identity.could(ctx, user, evidence.accept or reject, resource)`, the same `authorise`, walls included) | Design §5; security review M2; founder chose the recommendation (2026-10-07) | No |
| A decision is refused outside a live API request (`serving_request`) and bound to the session's actor in the database | An agent holding its initiator's `AuthContext` must still be unable to decide (security review H2) | No (ADR-005 enforcement) |
| A version fulfilling several items is queued once, for its first item | Retrievals fulfil one item; multi-item versions are an edge case for increment 6 | No |
| TASK-019 is stacked on TASK-018c (migration 0015 follows 0014) | Avoids two Alembic heads; rebase onto main after 018b and 018c merge | No |

## Gotchas and discoveries
-

## Questions for the human
- Design questions D1–D5 (above).
- SPEC-004 open questions Q1–Q8.
- Glossary entries "review queue" and "reason code" (protected).

## Handoff
- **Current state:** implemented on `task-019-review`, stacked on `task-018c-admission`. Independent tests are deferred, by the founder.
- **Next:**
  1. Run the security and architecture reviews.
  2. After 018b and 018c merge, rebase onto main and open the PR (red: the founder's line-by-line review).
  3. Add the independent tests when the founder asks.
