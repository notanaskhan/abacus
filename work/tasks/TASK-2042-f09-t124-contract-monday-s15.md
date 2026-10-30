---
id: TASK-2042
title: F-09-T124 S15 programme cadence (Contract Monday)
spec: SPEC-049
acceptance_criteria: [AC-34]
risk_zone: green
status: blocked
epic: F-09
plan_key: F-09-T124
branch: s15c-f09-t124
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50, vendor tracker and spend ledger
refresh, vendor reviewer replies; the note lists every open application, contract and partner with
its status, and any fired trigger has its pre-agreed action that day.

## Built
- `abacus_tools.contract_monday`: the note from the tracker (open rows, past-due flags) and the risk
  register (each named trigger's signal and contingency, "Fired?" for a person), plus the ledger and
  replies checklist. Reads only; writes no status, decision, price or name.
- `docs/ops/programme/contract-monday/README.md`: how the note is made each sprint and its log.
- SPEC-049 AC-34; tests `backend/tests/unit/tools/test_contract_monday.py` (run at the end review).

## Finding
On 2026-10-30 all 30 tracker rows still read `to file` (the tracker has not been updated in git since
S0). A note now would mark 27 past due. Either the tracker is stale or the applications are late;
only AY can say, from the vault.

## Blocked on
AY's refreshed tracker statuses, the spend ledger review (vault) and the reviewer replies: the
S15 note is written on the sprint's first day from them.

## Progress log
- 2026-10-30: tool, notes folder and AC built.
