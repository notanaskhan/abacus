---
id: TASK-6208
title: A-07-T24 representation letter service
spec: SPEC-000  # A-07 F3 (docs/plan/epics/A-07.md)
acceptance_criteria: [AC-1]  # Oct 9 G7; Oct 8 date mismatch; send refused before approval
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T24
branch: s31-a07-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (amber)
- `assurance/rep_letters.py`: compose from the published C11 `representation_letter` template
  (`reporting.api.published_clauses`): general 1-11 locked, specific 12-15 as clauses keyed by
  trigger; triggers registered per key (late remittance, certified investments, related party,
  going-concern doubt); insert-only versions with content hash and the SUM snapshot; include
  toggles and edits (clauses only, sealed, no amounts) as new versions; request approval; EP
  approval (human, fresh MFA, seen hash); send refused before approval, dated as of the report
  date; G7 or date mismatch on `envelope.completed` (client signer's instant in the firm's zone).
- A-07-T19's `envelope.completed` hook records G7 for rep letters (inert until `audits.letters`).
- Seed: specific representations become C11 clauses (content stays in the template).
- `signatures.api.envelope_signing` exported.
- Tests: `tests/unit/assurance/test_a07t24_rep_letter.py` (run at the end pass).

## Partial
- The routes and the C7 draft/send under the partner's grant are wired with A-07-T33's flags
  (`rep_letter_documents`/`signers` stay NotLive); `mark_sent` is the service the route calls
  after C7 accepts. Remind uses C7's own reminder. The re-date bring-down letter is a new version
  via `start_letter` after a mismatch.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2808 | Specific representations as C11 clauses keyed by trigger; no amounts in edits | no |
