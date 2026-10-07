---
id: SPEC-004
title: Review queues and review decisions
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-005, ADR-054, ADR-061, ADR-068, ADR-004, ADR-007, ADR-020, ADR-026, ADR-027, ADR-031, ADR-063]
related_specs: [SPEC-000, SPEC-002, SPEC-003]
created: 2026-10-07
updated: 2026-10-07
---

> **Amended 2026-10-07 during TASK-019** (founder-approved design D1–D5, and the review fixes):
> - **Decision routes:** three, one per matrix action: `…/decision/accept` with `evidence.accept`; `…/decision/reject` and `…/decision/send-back` with `evidence.reject`. Bodies carry `reason_code` (reject and send back only), `note`, and `seen_proposal`: the proposal the reviewer was shown. If the agent's latest proposal differs, the decision answers 409 `proposal_changed`, so a correction is always against what the person saw.
> - **Reason codes:** `GET /v1/engagements/{id}/review-reason-codes/{reject|send_back}` (D3).
> - **Reject:** moves the item to `open`. The rejected version was its newest, so nothing older is reviewable (Q2 refined).
> - **Several items:** a decision moves every item its version fulfils.
> - **Who decides:** only in a live API request, bound in the database to the session's actor (ADR-005).
> - **New evidence after a send back:** a sent-back item takes new evidence and becomes `received`.

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Evidence that is ready for a human's judgement lands in a review queue for its engagement. A reviewer takes it, sees the agent's proposal (the screening result's handoff), and records a **review decision**: accept, reject, or send back. Reject and send back require a reason code from a catalogue. Decisions are human-only (ADR-005), insert-only and audited. Each decision, with its reason code and any correction to the agent's proposal, is stored for the Learning layer (Phase 1 §5.3: "storage of corrections and reason codes only"). This is the Trust-layer primitive "Review queues" of Phase 1 §5.3, and the decision half of Phase 2 increment 6.

## 2. Problem and context
Agents now propose (`screening_results`, with `ready_for_review` or `needs_revision`, confidence, rationale and verified citations), but nothing lets a person decide.
- **The gap:** ADR-005 draws the line ("only a human actor may create a `ReviewDecision`, accept or reject evidence"), and ADR-054 says reviewers "accept, edit or reject; rejections require a reason code", whose feedback "creates firm examples, candidate firm rules and evaluation cases". Neither the queue nor the decision exists.
- **Today:** a request item can reach `ready_for_review`, and then stays there.
- **What depends on it:** without the decision, Phase 2's increments 6 (accept, reject, send back), 7 (export of accepted evidence) and 8 (follow-ups from send-backs) have nothing to build on.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Reviewer (engagement partner, manager; senior where the firm allows) | Works the queue, takes items, decides |
| Engagement team (staff, reviewer role) | Sees the queue and decisions read-only |
| Agents (screener; later the engagement agent) | Propose only: their screening results and suggestions feed the queue; they can never decide (ADR-005) |
| Learning layer (later) | Reads stored decisions, reason codes and corrections (ADR-068); nothing in this spec learns |

## 4. Goals and non-goals
**Goals**
- A per-engagement review queue: evidence versions awaiting a human decision, ordered (Q3), with what the agent proposed.
- Taking an item (assignment to a reviewer) and releasing it, so two reviewers don't decide the same item.
- **Review decisions:** accept, reject or send back an evidence version.
  - Human-only, enforced in the service and by a database CHECK (ADR-005).
  - Insert-only (ADR-004).
  - Audited (ADR-007).
  - A reason code is required for reject and send back (ADR-054).
- A reason-code catalogue (Q1).
- **Corrections:** when the reviewer's decision differs from the agent's proposal, the decision records that (ADR-054 "edit"). Corrections and reason codes are stored, and nothing more is done with them yet.
- **Decision effects on the request item:** accept and send back move the item's status (§6). Reject leaves the item awaiting evidence.

**Non-goals**
- The learning loop itself: examples, firm rules and evaluation cases from corrections (ADR-068, Phase 2+).
- Follow-ups sent to clients on a send-back (Phase 2 increment 8). Send back only sets the item's status.
- Suggestions other than screening results (the `suggestion` table and `suggestion.resolve`). These come with the engagement agent (increment 8), and Q5 covers the overlap.
- The full review UI (increment 6). This spec has the API plus a minimal queue screen (Q6).
- Sign-off, second-level review and quality-partner review workflows.
- Changing an accepted item (ADR-005 lists it as human-only, but it needs a reopen flow; deferred).

## 5. User stories and acceptance criteria
### Story 1: As a reviewer I want one place listing what needs my judgement
- **AC-1** Given an engagement with evidence versions that have no review decision, when a reviewer opens the engagement's review queue, then each such version is listed once with:
  - its request item;
  - the agent's proposal, if any (action, confidence, rationale, verified citations, unverified points);
  - its provenance summary;
  - who has taken it, if anyone;
  - ordering per Q3.
- **AC-2** Given a version superseded by a newer one for the same item (ADR-004), then only the newest undecided version is queued. The superseded one is not.
- **AC-3** Given the queue, it is filtered by `visible()` with the review read action, so walled people (SPEC-002) and people without the role see nothing of it.

### Story 2: As a reviewer I want to take an item so no one else decides it at the same time
- **AC-4** Given an unassigned queued version, when a reviewer takes it, then it shows as theirs. A second reviewer trying to take it gets 409 `already_taken`.
- **AC-5** Given an item taken by someone, when they release it, or an engagement partner or manager reassigns it, then it is unassigned, or assigned to the new person. Each change is audited.

### Story 3: As a reviewer I decide, and my reasons are kept
- **AC-6** Given a queued version, when a permitted reviewer accepts it, then a review decision is recorded (actor, time, decision, the screening result it responds to), `review_decision.created` is audited, the version leaves the queue, and its request item becomes `accepted` (Q2).
- **AC-7** Given a queued version, when the reviewer rejects it, then a reason code from the catalogue is required (422 without one, or with an unknown or retired code). The item returns to `received` or `open` (Q2), awaiting new evidence.
- **AC-8** Given a queued version, when the reviewer sends it back, then a reason code is required, and the item becomes `needs_revision`. No message is sent (increment 8).
- **AC-9** Given an optional free-text note on any decision, then it is stored classified confidential, length-limited, and never logged.
- **AC-10** Given the decision differs from the agent's proposal, then the decision is marked as a correction of that screening result:
  - accepting what the agent said needs revision;
  - sending back or rejecting what it called ready.

  It is stored as such for the Learning layer.
- **AC-11** Given a version that already has a decision, when anyone tries to decide it again, then 409 `already_decided`. A decision is never updated or deleted.

### Story 4: Only humans decide
- **AC-12** Given an agent or system context, when it calls any decision function or route, then it is refused (`Forbidden`), and the database refuses a decision row whose actor isn't human (ADR-005 enforcement).
- **AC-13** Given a person without the decision right on that engagement (matrix: `evidence.accept`/`evidence.reject`; seniors only where the firm setting allows), then 403 and nothing recorded. Given a walled person, then 404 (SPEC-002).

### Story 5: The catalogue
- **AC-14** Given the reason-code catalogue (Q1), when a reviewer lists codes, then they see the active codes for the decision kind (reject or send back), each with a code, a label and a description.

## 6. Behaviour and flows
**Happy path**
1. Retrieval produces an evidence version, and screening proposes `ready_for_review` (or `needs_revision`).
2. The version appears in the engagement's queue (derived: undecided, newest version of its item).
3. A reviewer takes it (`POST …/review-queue/{version_id}/take`).
4. The reviewer reads the proposal and decides (`POST …/evidence-versions/{version_id}/decision`, with `{decision, reason_code?, note?}`).
5. In one unit of work: authorise, insert the decision (human-only), move the request item's status, and record the audit event. The version leaves the queue.

**Item status effects** (Q2)
| Decision | Request item status after |
|---|---|
| accept | `accepted` (new) |
| reject | `received` if the item has other undecided evidence, else `open` |
| send back | `needs_revision` |

**State transitions** (an evidence version's review state; derived, not stored)
| From | Event | To | Who can trigger |
|---|---|---|---|
| (new version) | created | queued | system |
| queued | take, release, reassign | queued (assignee changes) | reviewer, or a manager reassigning |
| queued | decide | decided | permitted human only |
| queued | superseded by a newer version | not queued | system |

## 7. Domain and data changes
- **New table `review_decisions`**, owned by a module (Q4):
  - columns: `tenant_id`, `id`, `engagement_id`, `evidence_version_id`, `request_item_id`, `decision` (accept, reject, send_back), `reason_code` (nullable; required for reject and send_back, by CHECK), `note` (nullable, confidential), `screening_result_id` (nullable), `corrects_proposal` (bool), `actor_kind` (CHECK `= 'human'`, ADR-005), `actor_id`, `created_at`;
  - one decision per evidence version (UNIQUE);
  - insert-only and forced RLS.
- **New table `review_assignments`**: `tenant_id`, `evidence_version_id` (PK with the tenant), `assignee_user_id`, `assigned_by`, `assigned_at`. Updated on take, release and reassign; every change audited. This is operational state about who is looking, not a decision.
- **Reason codes:** a platform catalogue `review_reason_codes` with `code`, `applies_to` (reject, send_back), `label`, `description`, `active`. It is seeded by migration and has no tenant (Q1).
- **Request items:** the status gains `accepted` (Q2). Moves are forward-only per the table in §6.
- **Glossary:** "review queue" and "reason code" are added (glossary is protected: founder).

## 8. Interfaces
| Method | Path | Action | Notes |
|---|---|---|---|
| GET | /v1/engagements/{id}/review-queue | review.read (Q7) | the queue (AC-1–3) |
| POST | …/review-queue/{version_id}/take | review.take (Q7) | 409 `already_taken` |
| POST | …/review-queue/{version_id}/release | review.take | the taker, or a manager or partner |
| POST | …/review-queue/{version_id}/assign | review.assign (Q7) | `{user_id}`; partner or manager |
| POST | /v1/engagements/{id}/evidence-versions/{version_id}/decision/accept | evidence.accept | `{note?, seen_proposal?}` → 201; 409 `already_decided`, `superseded` or `proposal_changed` |
| POST | …/decision/reject and …/decision/send-back | evidence.reject | `{reason_code, note?, seen_proposal?}` → 201; 422 `invalid_reason_code` |
| GET | /v1/engagements/{id}/review-reason-codes/{reject\|send_back} | review.read | the catalogue (AC-14) |

Module interface: `decide(ctx: AuthContext, version_id, decision, reason_code, note)`. It takes only an `AuthContext`, so agent and system contexts can't even type-check into it (ADR-005).

## 9. Authorisation and tenancy
- **Decide:** `evidence.accept` for accept, and `evidence.reject` for reject and send back. The matrix already denies agents (ADR-005). Seniors are allowed only by the firm setting `seniors_can_accept` (a `firm_setting(...)` condition, which denies until firm settings are modelled; Q8).
- **Queue reads and taking:** new matrix actions (Q7). It is a protected change, so it needs approval.
- **Lists:** `visible()` with the read action and the engagement column (ADR-027, ADR-102). Walls apply (SPEC-002): a walled person gets 404.
- **Tenancy:** every new table is tenant-scoped with forced RLS. The reason-code catalogue is global and read-only (Q1).
- **Agents:** no agent action. The decision service accepts only `AuthContext`, the database CHECK enforces `actor_kind = 'human'`, and an agent-context test proves refusal (ADR-005 enforcement).

## 10. AI behaviour
N/A: no model calls. The queue shows the screener's existing handoff (ADR-054). Corrections are stored, not used (ADR-068 is later).

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **Two reviewers deciding at once:** the UNIQUE (tenant, version) constraint lets one win, and the other gets 409 `already_decided`.
- **Deciding without having taken the item:** allowed for permitted reviewers (Q3). Taking is coordination, not a lock on the right to decide.
- **A new version arrives while the old one is taken:** the old one leaves the queue (AC-2) and its assignment goes with it. The new one is queued unassigned.
- **A decision on a superseded version:** refused, with 409 `superseded`.
- **Archived engagement:** read-only (an existing attribute layer), so decisions and taking are refused.
- **A walled reviewer:** 404 everywhere (SPEC-002).
- **A reason code retired after use:** past decisions keep it, and new decisions can't use it.

## 13. Security and privacy
- **Data classification:**
  - decisions are internal;
  - the free-text note is confidential (it may discuss client data) and never logged;
  - reason codes are public.
- **PII:** none beyond user IDs.
- **Threats:**
  - an agent or compromised automation making decisions, mitigated in three layers (service type, matrix, database CHECK);
  - deciding someone else's taken item, which is allowed by design (Q3) and audited;
  - a decision on another firm's evidence, prevented by RLS and the `visible`/`authorise` checks;
  - existence leaks to walled people, prevented by the 404.

## 14. Audit trail and evidence integrity
- **Audited:** `review_decision.created`, carrying the decision, the reason code and the correction flag, and `review.taken`, `review.released` and `review.assigned`.
- **Never changed:** decisions are insert-only and evidence versions remain unchanged (ADR-004).
- **Provenance:** the decision links the exact version and the screening result it responded to, so what was accepted is provable.

## 15. Observability
- **Logs:** `review.decided` (decision, reason code, correction flag, IDs only) and `review.taken`.
- **Metrics:** decisions by kind and reason code, the correction rate (ADR-054 feedback quality), and queue size per engagement.

## 16. Performance and scale
The queue is a derived query over evidence versions without decisions, newest per item, filtered by `visible()`. Indexes cover (tenant, engagement) on decisions and assignments. The expected scale is hundreds of items per engagement.

## 17. UX
API first. A minimal queue screen in the SPA (Q6): a list with the agent's proposal, plus take, accept, reject and send back with a reason code. Full item detail with provenance and verified citations is increment 6.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1–3 | integration | Queue contents, ordering, newest version only, walls and `visible()` |
| AC-4, AC-5 | integration | Take, conflict, release, reassign, audit |
| AC-6–11 | integration | Each decision's effects, reason code rules, note handling, correction flag, no second decision |
| AC-12 | unit + integration | Agent and system contexts refused by the service, the matrix and the database CHECK |
| AC-13 | matrix-generated | Every role on decide, take and read; walled people get 404 |
| AC-14 | integration | Catalogue listing per decision kind |

## 19. Rollout
No flag: the queue appears once the routes ship. The migration is additive, adding `accepted` to the item statuses. The reason-code catalogue is seeded by the migration.

## 20. Open questions
None. Answered by the founder on 2026-10-07 (all recommendations):
- [x] **Q1: the reason-code catalogue.** A platform catalogue seeded now, firm-extensible later, or firm-defined from the start? *Recommendation: a platform catalogue seeded by migration (for example, wrong period, wrong entity, incomplete, illegible, doesn't agree to the ledger, unsigned, other with a required note). Firm-specific codes come with firm settings. Codes are never deleted, only retired.*
- [x] **Q2: request item statuses.** Add `accepted`, and decide where reject leaves the item. *Recommendation: add `accepted`. Reject returns the item to `received` if it has other undecided evidence, otherwise to `open`. Send back sets `needs_revision`.*
- [x] **Q3: queue ordering, and whether taking is required before deciding.** *Recommendation: order by the agent's proposal (`needs_revision` first, then lowest confidence), then oldest. Taking is advisory coordination: any permitted reviewer may decide, and the decision records who.*
- [x] **Q4: which module owns `review_decisions`, the assignments and the catalogue.** The candidates are `evidence` (decisions are on evidence versions) or a new `review` module under `audit_trail`/`requests`. *Recommendation: the `evidence` module owns decisions and assignments, since the decision is on its versions. `requests` exposes the item-status move through its api (no cross-module tables). The catalogue is owned by `evidence`.*
- [x] **Q5: screening results versus suggestions.** ADR-005 names both `ScreeningResult`s and `Suggestion`s as agent proposals, and the matrix has `suggestion.resolve`. *Recommendation: in this spec, a review decision responds to a screening result. Suggestions, with `suggestion.resolve`, arrive with the engagement agent (increment 8) and reuse `review_decisions` with a `suggestion_id`.*
- [x] **Q6: SPA scope.** API only, or a minimal queue screen? *Recommendation: a minimal queue screen (a list, take, and decide with a reason code), so the loop is demonstrable on staging. Full item detail is increment 6.*
- [x] **Q7: new matrix actions.** *Recommendation:*
  - `review.read` (engagement partner, manager, senior, staff, reviewer; in scope for practice leader and quality partner);
  - `review.take` (partner, manager, senior, and staff only if the firm allows);
  - `review.assign` (partner, manager).

  Agents are denied on all three.
- [x] **Q8: seniors deciding.** The matrix gates seniors on `firm_setting(seniors_can_accept)`, which denies until firm settings exist. *Recommendation: leave it denying (seniors can't decide yet). Model firm settings in their own spec.*

## 21. Future / explicitly deferred
- **The learning loop:** examples, candidate firm rules and evaluation cases from corrections (ADR-068).
- **Follow-ups on send-back** (increment 8).
- **Reopening an accepted item** (human-only, with a reason).
- **Second-level and quality-partner review,** and sign-off.
- **Suggestions beyond screening results** (Q5).
- **Firm-defined reason codes,** and firm settings such as `seniors_can_accept`.
