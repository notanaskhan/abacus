---
id: TASK-8359
title: "T-07-T27: The row's rest: L4 values approval partner-only, the election and a question send human-only"
spec: SPEC-656
acceptance_criteria: [AC-12, AC-13]
risk_zone: amber
status: in-review
branch: t07t27-human-only
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T27
---

## Objective
Spec section: SPEC-656 TXT-03/TXT-04 human-only rules. The row's rest: L4 values approval partner-only, the election and a question send human-only.

## Plan (amber)
1. `tests/unit/tax/test_t07t27_human_only.py`: the matrix's `sign_off.partner` allows only the engagement partner; `fiduciary_election.record` and `request_item.send` deny the agent and the system; no client role records the election; TXT-04's header offers `sign_off.l4` only to the partner, nothing to a client or the agent.
2. Fix the finding: `estate_service._header` listed every action for every viewer; `offered()` now asks `authorise` per action (Approve values is `sign_off.partner`).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. 10 passed; ruff and pyright clean. The draft-K-1 property is covered against Postgres by T-02-T26 and T-07-T28 (same `k1_documents`). The trustee question's route is still a stub, so its send stays a matrix-level check. Gates and
  tests run once at the S47 end pass (build first, test last).
