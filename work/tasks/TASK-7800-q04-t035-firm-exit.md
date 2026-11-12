---
id: TASK-7800
title: "Q-04-T035: firm exit runbook, the export check and the exit certificate, rehearsed on a rehearsal tenant"
spec: none (backlog row Q-04-T035; ADR-034, ADR-156, ADR-179; DEC-72)
acceptance_criteria: [Q-04-T035]
risk_zone: red
status: in-review
branch: lo38-q04-t035-firm-exit
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-12
updated: 2026-11-12
plan_key: Q-04-T035
---

## Objective
A firm can leave: flags off, a dual-approved firm export verified where the firm receives it, data
returned, and the per-tenant key crypto-shredded with a certificate naming both dates.

## Plan (red)
- `backend/src/abacus_tools/firm_exit.py` (tooling, never imported by `abacus`): `verify` (archive
  and manifest digests against the export row, every manifest entry, nothing unlisted, each A-01
  package through `package_check`) and `certificate` (from a passing report and the custodian's
  `ScheduleKeyDeletion` JSON). No AWS call, no database, no new dependency.
- `docs/runbooks/firm-exit.md`: decide, flags off, export (DEC-72), verify, crypto-shred, close.
- Tests: `tests/unit/tools/test_q04t035_firm_exit.py` (13), rehearsal
  `tests/integration/test_q04t035_firm_exit_rehearsal.py` (Q-02-T47's synthetic firm, real routes).
- DEC-4800. No migration, no flag, no route. Rollback: revert the commit.

## Acceptance
"The rehearsal tenant exits end to end with dual-approved export, verified checksums and a
certificate naming both dates": the rehearsal test. Open: the custodian's real key deletion on AWS
(no production stack) and counsel's exit terms.

## Progress log
- 2026-11-12: built; unit tests pass; rehearsal runs at the end pass.
