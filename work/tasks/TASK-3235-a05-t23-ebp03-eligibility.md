---
id: TASK-3235
title: A-05-T23 EBP-03 Eligibility testing, states a-e
spec: SPEC-640
acceptance_criteria: [AC-19, AC-20]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T23
branch: s26b-a05-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3235 · A-05-T23 · EBP-03 Eligibility testing

## Built
- Contract first (DEC-2225): `GET /v1/audits/{work_item_id}/ebp/eligibility/sample` (`ebp.read`, 501 until the sample service lands): `EligibilitySampleOut` / `EligibilitySampleRowOut`; client regenerated (two new schemas, no renames).
- `apps/web/src/screens/EBP-03/` (Eligibility canvas hook, copy, artboard, scenarios, test) mounted in the AUD-02 cockpit as Testing › Eligibility Testing (`ebp_03`): Dual-Source card (HR first-name chips, the row-22 hire difference with code's note), the matrix (masked DOB, hire, entry chip, rate, result: ✓, Flag + "Exception", "Needs human" + Mark no effect, spinner while testing with C6 polling and a 70 ms stagger), the computation line, the Exceptions card (code's missed amounts; Raise exception…, Request opt-out forms), Adopt (L1)… and Sign off… to SHL-12 on the attribute test; a row opens its PayGrid HR record in the viewer dock.
- Fixtures `seed/ebp03.ts` (the handoff's 25 rows) and scenarios a–e; 10 tests pass; AUD-02, EBP-02 and route suites unchanged (71 pass).

## Partial
- The sample service behind the contract (reading A-03's sample, the census, the HR records and the grid) is not built: the route answers 501 outside fixture mode.
- The Auto-Enrollment and Auto-Escalation provision cards (EBP-02's provisions) are not repeated here.
- Raise exception… and Request opt-out forms have no host wiring yet (AUD-15 draft finding, SHL-14 composer).
- Masked SSN with Reveal (logged) sits in the viewer's HR record, which is the evidence viewer's (not drawn in fixture mode).

## Progress log
- 2026-11-03: built; tsc and eslint clean; vitest 10 passed.
