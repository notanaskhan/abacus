---
id: TASK-1241
title: Accrued WISP v1 - 16 CFR 314.4 (a) to (j) and 201 CMR 17.00 mapped to the controls the code and docs run, the QI designation record, the Pub 5708-format appendix for firms (Q-02-T40)
spec: SPEC-341
acceptance_criteria: [AC-15, AC-23, AC-30, AC-38, AC-42]
risk_zone: amber
status: in-review
epic: Q-02
plan_key: Q-02-T40
branch: s8b-docs-compliance
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"The WISP is approved by the QI by Fri Apr 9 with every Safeguards element mapped to a control and its evidence." (Q-02-T40) This task writes v1; approval is the QI's and counsel's review runs through F-09.

## Plan (amber zone: document)
- `docs/ops/compliance/wisp.md`: purpose and scope; roles only (no names, addresses or vendor text); the QI designation restated from `README.md`; each 314.4 element with its control, location, evidence and state (operating, built, planned) taken from what `main` runs (SPEC-341's survey); a 201 CMR 17.00 crosswalk (17.03(2)(a) to (j), 17.04(1) to (8)); workstations; risk assessment; providers; enforcement; review cadence; an approval record; open items for counsel and for the builder; Appendix A in Pub 5708 shape for firms' WISPs, Brightwater Hale as the only example.
- Links: tracker row M7-09 in `README.md`; SEC-01 in `type-1-readiness.md`.
- **Rollback:** revert the commit.

## Progress log
- 2026-10-25: v1 drafted. Every element (a) to (j) has a control and an evidence line; seven of the controls are partial or planned, each named with its task (the MFA report and staff `amr` refusal, schedules, firm export, destruction, runbooks, the M4 programme items). Not marked approved.

## Questions for the human
- [ ] ayushkbhatia review of v1.
- [ ] Counsel (F-09): sufficiency under 314.4(f) and 201 CMR 17.00; the DPA notice time; Pub 1075 applicability; retention basis text; HIPAA posture.
- [ ] QI approval by Fri Apr 9, 2027.

## Handoff
- **Current state:** draft on this branch.
- **Exact next step:** review, then counsel through F-09.
