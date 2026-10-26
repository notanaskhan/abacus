---
id: TASK-1258
title: Acceptance and continuance live (CLI-07, human-only) (P-07-T35)
spec: SPEC-332
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T35
branch: s9a-engagement-lifecycle
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Daniel Reyes decides Thornbury with conditions and fresh MFA, Samuel Ito cannot decide at any
layer, and the record locks." Today every acceptance route in
`engagements/acceptance_contract.py` answers 501 (TASK-1196) and `start-acceptance` answers 501
(DEC-225). The row is BE only: the CLI-07 screen is P-07-T46.

## Plan (amber zone)
- **Migration 0163 `acceptance_v2`** (engagements; reversible, synthetic data only):
  - `acceptance_questionnaire_templates` (insert-only firm content: `name`, `family` tax ·
    audit_assurance · cas_advisory, `created_by`) and `acceptance_questionnaire_template_versions`
    (insert-only, immutable: `template_id`, `version_no`, `sections` jsonb array of
    `{code, title}`, `created_by`). Loaded by the scenario loader or a later admin screen, never
    by code (rule 16).
  - `acceptance_records` (one per engagement: `engagement_id` UNIQUE, `client_id`, `kind`,
    `template_version_id`, `prepared_by`, `status` C2 `acceptance_record`, `risk_rating`,
    `sent_to_partner_at/by`, `prescreen_run_id` reserved, `prior_record_id`, `version`); the app
    updates only status, risk rating, sent-to-partner and version, and a trigger refuses any
    update once the status is `decided` or `declined` (the lock at the database).
  - `acceptance_answers` (`record_id`, `section_code` UNIQUE together, `answers_sealed`,
    `state`, `version`, `updated_by/at`); `acceptance_manual_checks` (`requested_of`,
    `requested_by/at`, `completed_by/at`, `note_sealed`; completion once); both refused by a
    trigger once the record is locked.
  - Insert-only with `actor_kind`/`authored_kind = 'human'` CHECKs: `acceptance_flags`
    (`severity`, `title_sealed`, `body_sealed`, `source_refs`, `authored_by`),
    `acceptance_decisions` (`record_id` UNIQUE, `option`, `rationale_sealed`, `decided_by`,
    `decided_at`, `mfa_verified_at`), `acceptance_conditions` (`decision_id`, `position`,
    `text_sealed`, `assignee_user_id`, `due_on`), `acceptance_condition_events` (one
    `completed` per condition), `risk_partner_reviews` (events `requested` · `completed`).
  - Human-only register: `acceptance.decided` and `acceptance.review_completed` (0159's 33 + 2).
  - The repo's `engagement_acceptance` rows are not converted here (DEC-372): G1 reads the v2
    decision when the engagement has a v2 record and the legacy row otherwise, until P-07-T59
    converts and drops the legacy table with its adapter.
- **Service** `engagements/acceptance.py` (new): the record read (sections from the pinned
  template version merged with answers; flags, checks, decision, conditions, review, prior for a
  continuance), answers and risk rating, flags, manual checks, send to partner, conditions,
  risk-partner review request and completion, `decide_acceptance`, `start_acceptance` for a
  draft, and `g1_decision` for the gate. Free text sealed per tenant (`kernel.crypto.seal`) bound
  to its row. Every write one unit of work with one audit event; `acceptance.sent_to_partner` and
  `acceptance.decided` outbox events; `gate.met` G1 on accept.
- **Decision rules**: route authorises `acceptance.decide` (EP, `mfa_recent`, agent and system
  deny), then the service requires a live human (not a client, not break-glass support), then
  the record: locked 409 `decision_locked`; `seen_version` behind 409 `stale_version`; not
  Awaiting partner 409 `acceptance_not_ready`; empty rationale 422 `rationale_required`
  (`field: rationale`, every option: SPEC-332 AC-7 and the CLI-07 deviation win over OQ-6);
  Accept with conditions without a condition 422 `rationale_required` (`field: conditions`);
  conditions on another option 422 `invalid`; High risk without a completed risk-partner review
  409 `review_required`. Then one decision row, the conditions, the record `decided`/`declined`
  and the engagement Prospect → Accepted / Declined through F-03's transition table.
- **Gate**: `gates._acceptance`, the draft G1 (`drafts.py`), `record.gate_views` and the
  recorded letter read `g1_decision`; a letter dated before `decided_at` stays 409
  `letter_before_acceptance`, and a declined engagement 409 `gate_unmet` G1.
- **Adapter**: SPEC-025's `PUT …/acceptance` keeps working for engagements with no v2 record;
  with one, it refuses a decision that differs from the v2 decision (409 `decision_locked`).
- **Start acceptance** (`POST /v1/engagement-drafts/{id}/start-acceptance`, `client.intake`):
  behind `engagements.v2` and `engagements.acceptance_v2`; the draft's client entity, type,
  name, period and a team with an engagement partner (422 `draft_incomplete` otherwise); a
  Prospect engagement with the draft's team and a record pinned to the firm's newest template
  version for the type's family (409 `acceptance_template_missing` when the firm has none); kind
  `continuance` with a prior engagement, `new_engagement_existing_client` when the client has
  another engagement, else `new_client`. A second call returns the same record.
- **New route** `POST …/acceptance/risk-partner-review/complete` (`acceptance.complete_review`,
  new: the derived `firm_partner`, authorised on the client so walls apply; agent and system
  deny): only the named risk partner completes it (AC-4 needs a completion and the contract had
  no route for it).
- **Matrix**: `acceptance.complete_review` (new); `client.intake` gains the derived
  `firm_manager` (TASK-1259 adds the cell). Banned pattern `ACCEPT-001`: only
  `engagements/acceptance.py` and `engagements/acceptance_contract.py` name
  `decide_acceptance`.
- **Errors**: `acceptance_template_missing` (409, new); the rest exist.
- **Contract**: `docs/contracts/acceptance-independence.md` (status, the completion route, the
  start-acceptance rules) and `engagements-v2.md`; `make generate`.
- **Tests**: P-07-T38's suite (TASK-1257) unmarked as it passes; the stub and consumer contract
  tests move the acceptance routes from STUBBED to LIVE; `tests/integration/test_acceptance_v2.py`
  for the database rules (lock triggers, CHECKs) and the adapter.
- **Rollback**: revert the commits; 0163 downgrades (drops the tables, restores 0159's
  register). The routes answer 501 again.

## Progress log
- 2026-10-26: planned.
- 2026-10-26: built. Deviations from the plan: the app still never inserts an engagement status;
  "Start acceptance" inserts and moves the row to `prospect` in the same transaction (the
  schema test that the app cannot insert `status` stands). Answers' `seen_version` is the
  section's (0 before the first answer); the record's version is the decision's and the send's.
  The legacy adapter refuses any decision other than the record's. Errors moved from the
  contract module to `acceptance.py` (the catalogue's `raised_by` follows). DEC-372.
  Tests: P-07-T38's acceptance suite, 23 markers removed, 24 pass; `test_acceptance_v2_rules.py`
  3 pass; stub and consumer contract suites updated (the acceptance routes LIVE, the completion
  route added); the update-column contract in `test_schema_check_db.py` gains the three
  mutable tables. Gates green (ruff, pyright, lint-imports, banned_patterns with ACCEPT-001,
  error_codes, validate_docs, scope_guards, fresh_mfa, check-heads, check-generated);
  `make generate` and the web type-check.
- 2026-10-26: `tests/unit/api/test_app_gates.py` did not list the new completion route as a
  200 route; fixed in the T37 commit (I did not run `tests/unit/api` before the T35 commit).
- 2026-10-26: security review (changes requested) and fix round, DEC-375, migration 0165.
  H1: answers, the risk rating and manual checks frozen once sent (409 `acceptance_sent`, the
  database too); `high_risk_seen` sticky, the review required whenever it is set; the audit
  carries the rating's positions before and after. M1: 0165's decision guard (Awaiting
  partner, the acting person, the engagement's partner-level EP, the review on a High record)
  and acting-person triggers on flags, condition events and review events; G1 needs the
  decided record. M3: start acceptance refuses a non-partner EP; the decider must be
  partner-level (service and database); the engagement-members trigger is a follow-up. L1/L2:
  the review completion reads the flag after authorising, and needs fresh MFA. L6: kept on
  api.py (P-07-T38 calls it there; ACCEPT-001 still guards it). Tests:
  `test_p07_security_review_fixes.py` (11), the rules tests adapted to 0165 (probes through
  the unit of work), P-07-T38 unchanged and passing.
- 2026-10-26: re-review follow-ups (notes on DEC-375; 0165 amended in place before main): a
  reviewer seated as an engagement partner since the request cannot complete the review, and
  the person who completed it cannot decide (service and database); `updated_by`,
  `prepared_by` and `run_by` are the acting person in the database; a check's outcome is
  `hits` whenever `restricted_match` is true. Tests: three new in
  `test_p07_security_review_fixes.py`, two outcome assertions moved to `hits`; P-07-T38
  unchanged. P-07 and schema suites 287 passed; gates green.
