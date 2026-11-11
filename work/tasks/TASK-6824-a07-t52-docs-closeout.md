---
id: TASK-6824
title: "A-07-T52 (partial): A-07 docs, skills and close-out; contract v1, consumer notes, flag retirement plan"
spec: SPEC-644
acceptance_criteria: [AC-52]
risk_zone: red
status: in-review
branch: s36-a07-t52
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: A-07-T52
---

## Objective
validate_docs is green, and a fresh session can add a guarded table and an exception kind from the
docs alone.

## Built
- `.claude/skills/backend-module/SKILL.md`: "A guarded table and an archived-write kind". It
  covers the automatic guard, the `EXEMPT` and `ALLOWED_KINDS` choices and the trigger migration,
  and the five steps for a new kind (ARCHIVE-001's exclude list, the tests both ways).
- `assurance/README.md` (release, clocks, lock, seal, additions) and `evidence/README.md`
  (COMPLIANCE and GOVERNANCE retention, the two evidence services past the guard).
- `docs/contracts/audit-completion.md`: v1 final, consumer notes for Q-05, X-01, A-10, A-08,
  A-09, T-06, R-02 and I-01, and the flag retirement plan into `assurance_completion`.
- SPEC-644 `updated`. DEC-3416.

## Partial
- Capacity-ledger actuals are recorded at the S36 close, in `docs/plan/status/S36.md`.
- validate_docs runs at the end pass.
- The row depends on A-07-T51, which is itself partial: no staging rehearsal.

## Progress log
- `2026-11-11` — Docs written (S36). Nothing run.
