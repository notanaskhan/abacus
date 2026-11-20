---
id: TASK-8757
title: "C-01-T55: Docs and hand-offs: final SPEC and docs/contracts/closes.md; docs/screens/ for the nine screens with Deviations; closes README; runbook 'September close shadow and close support'; hand-off notes to C-02, K-04, W-02, W-03 and I-01; flag retirement PR plan; capacity ledger and task log"
spec: SPEC-655
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s51-c01t55
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-01-T55
---

## Objective
Each downstream epic's issue links its hand-off note, and every screen contract lists its deviations.

## Plan (amber)
1. Screen contracts for the six close screens that had none (CLS-02, CLS-03, CLS-04, CLS-05, CLS-06, POR-11): states → data with scenario keys, Parity (C-01 §5.4 Tier C locks, host Tier D), the handoff link graph's Links, and Deviations (DV-1…DV-8, QC-1, the C-01-T50 fixes). CLS-01, CLS-09 and CLS-10 already list theirs.
2. Runbook RB-93 `docs/runbooks/close-shadow-and-support.md`: what turns on, the gate, the daily shadow on PF-X1, close support answers, rollback by flags, rehearsal log.
3. Hand-off note `docs/plan/status/C-01-handoff.md` for C-02, K-04, W-02, W-03 and I-01, with the flag retirement plan and what stays open.
4. `backend/src/abacus/modules/closes/README.md`: the C-01 v1 routes, consumer API, compute, read-only rule, content rule, runbooks and hand-offs.
5. Also: every S51 task file's empty acceptance_criteria fixed (validate_docs rejects an empty list), and the recorder that wrote them.
6. Rollback: revert the PR (docs only).

## Progress log
- `2026-11-20` — Written, stacked on #2395; the link-contract and parity unit tests (80) and validate_docs pass. Not done: the downstream GitHub issues are not opened from this session (the note lists one per epic; opening them is the builder's call); RB-93 is not rehearsed on staging; SPEC-655 and docs/contracts/closes.md are unchanged (already approved and complete for v1); the capacity ledger lives in the plan's status notes, and this row's share is recorded here. Found in passing: TASK-8745…8756 had `acceptance_criteria: []`, which validate_docs (make check-fast) rejects; set to the convention `[AC-1]  # the backlog row's acceptance, quoted under Objective` (G-04-T21: SPEC-681 AC-15). Gates and tests run once at the S51 end pass (build first, test last).
