---
id: TASK-2301
title: A-03-T24 ADR P-63 multi-entity engagements and consolidation
spec: SPEC-540
acceptance_criteria: [AC-2]
risk_zone: red
status: in-review
epic: A-03
plan_key: A-03-T24
branch: s18-a03-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Draft ADR P-63 (DEC-65, DEC-66): engagement entities, `ledger` owning account mappings and
consolidation while staying dependency-free, the grouping and FS-line taxonomy as firm content,
one mapping set per entity's trial balance of record, eliminations as adjustments.

## Plan
- Prerequisite F-02-T02 is on main. Stacked on s18-a03-t23 (#748) for SPEC-540.
- Number: the plan's "ADR-154" is a P-ID alias and is P-67 on main; take ADR-341 from the S18 block.
- Reconcile with what is built: `engagement_entities` (0068), entity-scoped connections (0195),
  account mapping first slice (SPEC-316, 0079, rules computed on read). The ADR replaces A-03 §4.2
  M-B's stored `account_mappings`/`account_mapping_events` with the built design; missing state is
  added expand-only by A-03-T06.
- Files: `docs/adr/ADR-341-multi-entity-engagements-and-consolidation.md` (proposed), README index,
  backlog row P-63, decision-log DEC-65/DEC-66 ADR column, SPEC-540 related_adrs. No code.
- Tests: none (DOC); `validate_docs` at the end review.
- Rollback: revert the branch.

## Per AC
| AC | Evidence |
|---|---|
| AC-2 | ADR-341 (proposed) records DEC-65 and DEC-66; backlog row P-63 → ADR-341; decision-log rows link it |

## Progress log
- `2026-10-29` — ADR-341, README, backlog and decision-log rows. Held for the S18 batch.

## Questions for the human
- [ ] Accept ADR-341 (for both deciders: the builder and the audit CPA). Due Fri Jul 23, 2027.

## Handoff
- **Current state:** drafted (proposed), PR open, held for the S18 batch.
- **Exact next step:** on acceptance flip status, README index and backlog row to accepted; A-03-T06 adds the mapping state expand-only.
