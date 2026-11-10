---
id: TASK-6213
title: A-05-T57 AUD-27 estimates, related parties and parties in interest
spec: SPEC-640
acceptance_criteria: [AC-1]  # registry status words only; the agent never concludes
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T57
branch: s31-a05-t57
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan
- Contract, additive (`assurance/ebp_contract.py`): `Aud27ItemOut` gains account ref, significant
  risk, method text, disclosure ref, components, method tie, rollforward, retrospectives, range,
  bias, source, relationship, finding, exemption, reporting; `Aud27ListOut.prohibited`. The three
  read routes now return A-05-T53's views (parties in interest answered an empty list before).
  `aud27.estimates` reads significant risk, method text, disclosure ref and component labels.
- Screen `apps/web/src/screens/AUD-27/` (canvas `useEstimatesCanvas`, copy verbatim from the
  handoff, statuses through the `aud27_item` registry), composed in AUD-02 as `estimates_rp`.
- Fixtures `fixtures/seed/aud27.ts`, scenarios a–e and off; test `AUD-27.test.tsx`.

## Partial (DV-AUD-27-2 to 5)
- Transactions and disclosure columns, rollforward dates and the citation and procedure counts
  wait for those fields on the read; the dock is the cockpit's.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2813 | Additive AUD-27 read fields; the sponsor's PT exception derived on read | no |
