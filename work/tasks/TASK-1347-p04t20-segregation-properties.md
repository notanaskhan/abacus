---
id: TASK-1347
title: Independent AC and property tests (ADR-078) for I-SEGREGATION and the sign-off invariants (P-04-T20)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T20
branch: s10c-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s10c-tests (after P-04-T18/T19 landed in #429; written from the sources below, the code read only for routes and fixtures)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Property tests over random sign-off sequences, written in ayushkbhatia's session, find no
accepted sequence that breaks R-SO-1 to R-SO-6." Preparer never L2/L3, EQR never L1-L4, EP never
EQR, open notes block L2 and above, staleness by hash, five-layer human-only.

## Plan (red)
- **File (tests only):** `backend/tests/integration/test_p04t20_sign_off_properties.py`.
- **Sources only:** P-04 §3 F2 (SHL-12 a-h), the R-SO table (`docs/plan/03-backend-architecture.md`
  §3.7 and §4.7), ADR-160 clauses 2 to 4, `docs/contracts/review-grammar.md` §2 and the live
  paragraph (order of the fixed codes), `permission-matrix/review.yaml`, DEC-216, DEC-400 to
  DEC-402.
- **Boundary:** `create_app()` over HTTP as each person (`current_context` overridden, the
  `review.grammar_api` flag on); a test-owned reviewable type (`p04t20_probe`) whose facts the
  test sets (preparers, required fields, uncited values, hash), as the owners' facts slot allows
  (DEC-216); review notes as rows; the database layer as raw SQL; the call-site rule through
  `banned_patterns`.
- **Property:** hypothesis draws the target's facts and a sequence of up to 10 attempts (person,
  level, actor kind, seen hash, an edit that changes the hash). Every accepted row is checked
  against R-SO-1 to R-SO-6 from the matrix and the spec (a model written here, not read from
  the code); every attempt a rule forbids must be refused with a fixed code; rows are never
  updated; every row carries the hash current when it was signed.
- **No production change, no migration, no flag or matrix edit. Rollback:** delete the file.

## Progress log
- 2026-10-27: planned and written.
