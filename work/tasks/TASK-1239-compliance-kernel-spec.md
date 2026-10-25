---
id: TASK-1239
title: Compliance kernel and real-data readiness SPEC-341 and the compliance-kernel contract v1.2, written against what main has built (Q-02-T04)
spec: SPEC-341
acceptance_criteria: [AC-1, AC-15, AC-17, AC-23, AC-26, AC-30, AC-34, AC-38, AC-42, AC-44]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T04
branch: s8b-docs-compliance
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"The SPEC is approved by ayushkbhatia with no open questions and the contract doc names every consumer epic, its sprint and the fail-closed behaviour of each slot." (Q-02-T04)

## Plan (red zone: documentation only, no code)
- **Survey first.** Most kernel rows shipped before the spec (TASK-416, 417, 919, 920, 940, 965, 968, 1013, 1014, 1160, 1170, 1200, 1201). Map each of the epic's AC-1 to AC-46 to the migration, module and test that holds it.
- **Spec.** `docs/specs/SPEC-341-compliance-kernel-real-data-readiness.md`: keep the epic's AC numbers (tests on main already cite "Q-02 AC-n"), mark each **built**, **partial** or **not built** with file references, use the as-built names (DEC-227's `retention_policy.read`/`update`, the access kind `model_context.built`, the hold events `legal_hold.counted`/`activated`). Status `draft`: approval and the counsel questions are the human's.
- **Contract.** `docs/contracts/compliance-kernel.md` v1.2 adds §8 (each kernel slot, its consumer epics and sprint, its state and how it fails closed) and a changelog; the register row in `docs/contracts/README.md` follows.
- **Rollback:** revert the commit.

## Progress log
- 2026-10-25: written. Survey result: 26 ACs built, 15 partial, 5 not built (AC-10, AC-13, AC-41, AC-44, plus the independent suites noted per AC). The largest gaps: the Temporal Schedules for checkpoints, verification, anchors, the retention clock and access-event partitions (all wait on Q-01-T26), the live firm export (Q-02-T43), run records (Q-02-T41), and `make mfa-report`. Task files for the rows not yet started are not minted here: each takes the next free number when it starts (this branch holds five numbers).
- `backlog.csv` still reads `todo` for many built Q-02 rows (T16, T17, T20 to T24, T29, T30, T32, T33, T37, T38); the SPEC's per-AC state is the current picture. Not changed here: the status reconcile belongs to the main session.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-362 | The spec keeps the epic's AC numbers and the code's names; status draft until approved | No |

## Questions for the human
- [ ] Approve SPEC-341 (the row's acceptance), after the §20 questions.
- [ ] Counsel: legal floors per record type and service line (Q-02-T31); the 72-hour notice SLA in the DPA; the retention basis text under 314.4(c)(6).
- [ ] The Brightwater Hale incident reference (see TASK-1242).
- [ ] Whether the five scheduled jobs land before M7 or take the epic's cut order.

## Handoff
- **Current state:** spec and contract written; awaiting approval.
- **Exact next step:** answer §20, then set SPEC-341 to `approved`.
