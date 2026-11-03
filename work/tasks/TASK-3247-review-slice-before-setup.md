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

# TASK-3247 · The `review` slice loads past Apr 13 (DEC-2228)

AC-1: `make seed-demo --slice review` loads; Kevin Osei's two Feld checkpoints keep their SHL-16
dates (Apr 13 and Sep 11).

Found in S26 (A-04-T28): Checkpoint 1 "Extension estimate (4868)" replayed at Apr 13, before the
setup instant (Sep 1) that creates the firm, Kevin and the Feld return, so the load stopped there.
The event now replays at `max(date, SETUP_AT)` and carries `saved_at`; the handler saves under
`frozen(saved_at)`, so `abacus_now()` stamps the row with its own date.

## Progress log
- 2026-11-04: built; unit order test and a loaded test (`test_p04t36_review_loaded.py`).
