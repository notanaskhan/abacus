---
id: TASK-1289
title: G-02 gate check, SPEC-349 firm governance v1, ADR-186 (P-49) and ADR-187 (P-08)
spec: SPEC-349
acceptance_criteria: [AC-1, AC-49]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T01
branch: s9c-governance
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Gate check for G-02 and the firm governance SPEC with AC-1 to AC-49, the supersession table, the
Q-02 hand-off checklist, the revision R2 owners and the contract requests (G-02-T01).

## Plan
- **ADRs.** The row asks to confirm ADR-148 (P-49) and ADR-149 (P-08) Accepted. On `main` those
  numbers are P-28 and P-26 (plan aliases); `docs/adr/` and chapter 09 have no ADR for P-49 or
  P-08 (`docs/adr/backlog.md`: "to draft"). Draft them under the reserved numbers: ADR-186 (P-49,
  DEC-50 b) and ADR-187 (P-08, DEC-53 b). Both have a proposed option in the plan, so both are
  Accepted citing the solo amendment item 7. Backlog, ADR README, DEC-50 and DEC-53 rows point at
  them.
- **SPEC-349** (`docs/specs/SPEC-349-firm-governance-v1.md`): AC-1 to AC-49 from G-02 §3, data
  changes, interfaces, authorisation, test plan, rollout, open questions (Q7 only), supersession
  (§21) and the gate check (§22: ADRs, Q-02 checklist, R2 owners, contract requests).
- **Decisions.** DEC-415: G-02 §11.2 Q1–Q6, Q8–Q14 with the recommended answers; Q7 stays open.
- No code, migration, flag or matrix row. Rollback: revert the commit.

## Progress log
- 2026-10-26: gate check done. ADR-186 and ADR-187 accepted; SPEC-349 approved with Q7 open
  (does not block T02–T07). Contract-request issues are not opened from this branch (no push):
  the main session opens audit-log v1, security-center v1 and ai-policy v1 at merge.
