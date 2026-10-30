---
id: TASK-2144
title: N-01-T20 ADR-078 independent AC tests for N-01 intake, triage and Files
spec: SPEC-000  # N-01-T20 row
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T20
branch: s16-n01-t20
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Acceptance (backlog row): "Suites ... prove INV-3 and INV-4 on every inbox and Files read, and
I-AGENT-NEVER covers inbox.file, inbox.triage, inbox.match_sender and inbox.ask_client."

## Plan
- `backend/tests/integration/backfill/test_n01_t20_independent.py` (group B's fixtures):
  I-AGENT-NEVER on the four human decisions (matrix); INV-3 404 on every inbox read of a walled
  client's thread, attachment and message, thread list and Files tree exclusion; INV-4 a client
  principal never reaches a firm inbox or Files read; T07 insert-only intake rows; T09 the same
  bytes flagged `duplicate_hash`, never refused; T18 bulk filing answers per attachment.
- Group B (`test_n01_group_b.py`) already covers T12 previews, T13 audited reads, T14 portal
  withdraw and T18 supersede and human-only apply; this suite adds what it lacks.

## Progress log
- 2026-10-30: written; the matrix test passes. The DB tests run at the end review.
