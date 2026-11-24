---
id: TASK-8911
title: "T-06-T42: Other-entity workpapers service and routes"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t06t42
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-06-T42
---

## Objective
AAA and shareholder allocation, provision with rate reconciliation and deferred inventory, Part IX with allocation basis, public support; read-only lock on Filed or Accepted (409 return_locked); Explain... creating an SHL-15 issue; time-study allocation run (agent extraction, code allocation, proposal). Acceptance: Bluestem answers 409 return_locked on any write, and Lakeshore's allocation lands only as a proposal a person adopts.

## Done
- tax/other_entities_service.py: aaa (E10 roll of the M-2 columns, shareholder %s, locked), provision (current + deferred = total, ETR, tally, unclassified), explain_item (SHL-15 issue on an unclassified item, a person's act), functional_expenses (E12 Part IX foot/crossfoot, program ratio, public support), start_allocation (time-study lines from imported percentages through E12 → a time_study_allocation proposal on a tax.return_analyst run; allocation_runs row), adopt_allocation (proposal adapter writes the lines on approval only); 409 return_locked on every write of a Filed/Accepted return
- Routes in entity_depth_contract.py wired; TaxDepthRunOut gains optional issue_id and proposal_id (run_id optional)
- Registered: proposal adapter time_study_allocation, suggestion target functional_expense_line; reviewed audit labels; error codes
- docs/contracts/other-entity-workpapers.md 'Built' section
- tests/unit/tax/test_t06t42_other_entities.py (9 pass)

## Progress log
- `2026-11-23` — Built in the S53 sequential stack (DEC-5913). The agent extraction (tax.return_analyst mode time_study_allocation, its eval section) and Explain's suggestion are T-06-T54/T-06-T46's; make generate at the end pass (TaxDepthRunOut changed).

## Plan (amber)
1. Service over 0966 rows with E10/E11/E12; locked check first on every write.
2. Allocation as a proposal only, with an adapter for adoption. 3. Rollback: routes back to 501.
