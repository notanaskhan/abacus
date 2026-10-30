---
id: TASK-2300
title: A-03-T23 ADR P-57 sampling engine
spec: SPEC-540
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: A-03
plan_key: A-03-T23
branch: s18-a03-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Draft ADR P-57 (DEC-81): a seeded, versioned, frozen in-product sampler that re-performs from
`(seed, population_hash, sampler_version)`, with import kept as a path.

## Plan
- Prerequisite F-02-T02 is on main. A-03 has no SPEC yet (its kickoff is S20): SPEC-540 carries
  T23 and T24's ACs.
- Number: the plan's "ADR-207" is a P-ID alias (`docs/adr/backlog.md`); take ADR-340 from the S18
  block (migrations 0460+, TASK-2300+, DEC-1350+, SPEC-540+, ADR-340+).
- Reconcile with what is built: `sampling/selection.py` `seeded_v1` (ADR-132, SPEC-037, TASK-083)
  is journal-entry selection and stays frozen; the P-57 sampler is a new compute library under
  `sampling/compute/` from A-03-T04, using only `getrandbits(32)` (A-03 F1).
- Files: `docs/adr/ADR-340-sampling-engine.md` (proposed), README index row, backlog row P-57,
  decision-log DEC-81 → decided, SPEC-540. No code, migration, flag or registry edit.
- Tests: none (DOC); `validate_docs` at the end review.
- Rollback: revert the branch.

## Per AC
| AC | Evidence |
|---|---|
| AC-1 | ADR-340 (proposed) records DEC-81; backlog row P-57 → ADR-340; decision-log DEC-81 decided with the link; SPEC-540 AC-1 |

## Progress log
- `2026-10-29` — ADR-340, SPEC-540, README, backlog and decision-log rows. Held for the S18 batch; `validate_docs` at the end review.
- `2026-10-29` — ADR-340 accepted (approved by ayushkbhatia in chat); status, README index, backlog and decision-log rows updated.

## Questions for the human
- [x] Accept ADR-340: acceptance approved by ayushkbhatia on 2026-10-29, for both deciders.

## Handoff
- **Current state:** accepted.
- **Exact next step:** on acceptance flip status, README index and backlog row to accepted; A-03's S20 SPEC cites ADR-340.
