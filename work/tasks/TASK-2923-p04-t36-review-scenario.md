---
id: TASK-2923
title: P-04-T36 Brightwater Hale review-grammar scenario events through service APIs
spec: SPEC-600
acceptance_criteria: [P-04 §3 artboard rows SHL-11, SHL-12, SHL-16; T36 acceptance]
risk_zone: amber
status: in-review
epic: P-04
plan_key: P-04-T36
branch: s24-p04-t36 (on s24-a04-t12)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-02
updated: 2026-11-02
---

## Objective

`make seed-demo` (`--slice review`) loads the review objects whose owners have registered, through the services as the people the design names, with real audit events.

## Acceptance (backlog)

make seed-demo loads every review object whose owner has registered by then (A-04 workpapers and materiality, T-01 return lines) through the APIs with real audit events, and make fixtures exports identical data.

## Plan (amber)

- Files: `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/review_slice.py` (events), `loader.py` (nine handlers, `SLICE_NEEDS`), `review.api` exports `create_issue`, `decide_card`, `raise_review_note`, `save_checkpoint` for the loader (as `sign_target`); `assurance.api` exports `propose_materiality`, `reassess_materiality`.
- Objects: Northwind PY2025 TB recorded and adopted (Hannah, Sep 8); Marcus L1 on it (Sep 14, 9:00); Hannah's and Margaret's notes RA!C14 / RA!C22 (SHL-12 copy, verbatim) assigned to Marcus; materiality proposed 9:27 (1.5% of net assets), decided by Margaret 10:02 (rate_1_5, rationale from the review seed), reassessed Oct 6 and No change; Ridgeline's 11 open issues from TXP-10 verbatim (5 waiting + 6 review points, block final approval); Feld checkpoints 1 and 5 saved by Kevin Osei.
- No migrations, no registry edits; flags `review.checkpoints`, `assurance.materiality` set by the slice.
- Tests: `backend/tests/unit/synthetic/test_p04t36_review_slice.py`; the loaded figures are P-04-T37's golden suite.
- Rollback: drop the slice from `SLICE_NEEDS`; nothing else reads it.
- Stacked on A-04-T12 (#1045): materiality's service lives there.

## Progress log

- 2026-11-02: built in abacus-s24; tests written, not run. DEC-1969 records what is not loadable yet. `make fixtures` parity is the end pass's (fixture export of review rows not wired).
