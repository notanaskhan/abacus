---
id: TASK-3247
title: Review slice loads past Apr 13 (Feld checkpoint dated before the setup instant)
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T36
branch: open-review-slice
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-04
updated: 2026-11-04
---

# TASK-3247 · The `review` slice loads past Apr 13 (DEC-2228, DEC-2229)

AC-1: `make seed-demo --slice review` loads; Kevin Osei's two Feld checkpoints keep their SHL-16
dates (Apr 13 and Sep 11).

Found in S26 (A-04-T28): Checkpoint 1 "Extension estimate (4868)" replayed at Apr 13, before the
setup instant (Sep 1) that creates the firm, Kevin and the Feld return, so the load stopped there.
The event now replays at `max(date, SETUP_AT)` and carries `saved_at`; the handler saves under
`frozen(saved_at)`, so `abacus_now()` stamps the row with its own date.

Two more stops behind it: slice needs were followed one level only, so `tax_board`'s
`binders` never loaded (now transitive); and the Sep 14 TB L1 met R-SO-5 before G2, which
DEC-1767 met on Sep 15. G2's four steps move to Sep 14 before E0 and `review` needs `sampling`
(DEC-2229).

## Progress log
- 2026-11-04: built; unit order test and a loaded test (`test_p04t36_review_loaded.py`).
- 2026-11-04: needs followed through; G2 re-timed to Sep 14 9:00–9:15 (DEC-2229).
