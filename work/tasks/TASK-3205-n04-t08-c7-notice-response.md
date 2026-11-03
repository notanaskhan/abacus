---
id: TASK-3205
title: N-04-T08 C7 additive for the notice response and QN-1's G3 rule
spec: SPEC-000  # row (N-04 has no SPEC yet)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T08
branch: s26-n04-t08 (stacked on s26-p11-t19)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"A notice-response envelope with the CP2000 response page as a one-page range completes in record
mode and on the DocuSign demo, and G3 reads met for the Whitley notice engagement through the
covering letter."

## Plan (red)
- C7 additive:
  - the `notice_response` source contract (purpose `notice_response`, family `general`);
  - the QN-5 identity floor for the purpose (email code, in person, firm SSO; never KBA);
  - `SourceDocument.page_from/page_to` and `EnvelopeDocumentOut` with the range;
  - migration 0656 on 0655, adding the columns and their CHECK;
  - `envelope.declined` gains purpose, source kind and source id.
- QN-1:
  - `engagements/notice_letters.py` `covering_letter_engagements`: a signed `tax_compliance`
    letter of the same client entity with `notice_support` on;
  - signatures' G3 provider (`sources.letter_gate`) meets G3 through a covering letter whose own
    G3 is met.
- Docs: `c7-envelopes.md` v1.2. `make generate`.
- Tests:
  - `tests/unit/signatures/test_n04t08_notice_response.py`;
  - `tests/integration/test_n04t08_page_range_migration.py`.
- Rollback: revert; `alembic downgrade 0655`.

## Progress log
- 2026-11-03: built. The DocuSign demo run is an ops check on the provider sandbox (F-09). The
  N-04 response source registers in N-04-T19. Tests at the S26 end review.

## Decisions made during this task
DEC-2205.
