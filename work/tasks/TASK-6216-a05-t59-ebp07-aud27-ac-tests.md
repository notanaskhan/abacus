---
id: TASK-6216
title: A-05-T59 independent AC tests and goldens for the EBP-07 and AUD-27 services
spec: SPEC-640
acceptance_criteria: [AC-1]  # 4i totals 16,812,400 with party-in-interest asterisks; a non-EP decide answers 403
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T59
branch: s31-a05-t59
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (amber: written before building)
- Files: `tests/unit/assurance/test_a05t59_ebp07_aud27_ac.py` (ADR-078: written from A-05 §3 and the
  handoff's figures); `compute/ebp/form5500.py` gains `HeldAsset`, `Schedule4iRow`, `Schedule4i`
  and `schedule_4i` (pure; no migration, no registry or flag edit).
- Goldens: the eight 4i holdings total 16,812,400 (seven parties in interest; cost omitted for
  seven participant-directed investments); 5500 net assets 16,812,400 = 14,228,500 + 2,583,900;
  only the 48,600 receivable (15,060 + 33,540) differs; Part IV 4a against 33,540.
- EP-reserved conclusion: the `estimate_conclusion` kind's `reserved_role` and the
  `decision.decide` rule's `reserved_role` condition refuse a non-holder (403) and every agent.
- One late-remittance record: one table, read in place by 4a, AUD-27 and EBP-04; nothing outside
  assurance names it.
- Rollback: delete the test file and the four engine names (nothing else imports them).

## Partial
- EBP-07's 4i read and C11 render call `schedule_4i` with `ebp.schedule.render` later
  (DV-EBP-07-3).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2816 | 4i schedule in code; ADR-078 AC goldens for EBP-07 and AUD-27 | no |

## Progress log
- 2026-11-08: written; runs at the S31 end pass.
