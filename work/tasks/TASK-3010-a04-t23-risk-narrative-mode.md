---
id: TASK-3010
title: A-04-T23 mode risk_narrative — prompt, mapping, presumed risks by code, PBC GAP flags
spec: SPEC-620
acceptance_criteria: [AC2.1, AC2.2]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T23
branch: s25-a04-t23 (stacked on s25-a04-t22)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"The Northwind draft cites 9 sources, prepopulates both presumed risks exactly, raises PBC GAP flags
only, and shows reserved actions absent 1.0."

## Plan (red)
- Slots: `register_mode_preparer`, `FLAG_MODES`, `SectionSource.raise_flag`.
- Drafter (PROTECTED): preparer at `start`; `_raise_flags` in the run's unit of work.
- `handoff.DraftedFlag`, `SectionDraft.flags`.
- `workpapers/drafting.raise_draft_flag`; `assurance/risks.presumed_preparer`, `prepopulate_presumed`;
  `draft_mappings.risk_narrative_inputs`; prompt v1; spec v5; codegen.
- Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| Own prompt, mapping, preparer | `tests/unit/agents/test_a04t23_risk_narrative_mode.py` |
| Both presumptions exactly; override never rebuttable | same |
| PBC GAP only, cited | same |
| 9 sources, reserved actions absent 1.0 | suite, fake route, `--mode risk_narrative` |

## Progress log
- 2026-11-02: built. TASK-3009 was skipped by mistake; this row takes TASK-3010.

## Decisions made during this task
DEC-2059.
