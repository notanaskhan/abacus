---
id: TASK-302
title: "Completion: deficiency severity, proposed entries (AJE/RJE) and the representation list"
spec: SPEC-301
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: done
branch: task-302-completion
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- Migration 0067: seven insert-only tables.
- `fieldwork/completion.py`.
- Findings now carry their deficiency state.
- Matrix: seven actions.
- schema_check, LIST_EXEMPT, and the pinned lists.
- Routes under `/findings/{id}/severity/*`, `/findings/{id}/communicated`, `/adjustments*` and `/representations*`.
- Web: the Findings tab gains a view switch (Findings · Proposed entries · Representations), a severity column, and the severity section in the drawer (`screens/Completion.tsx`).
- Rollback: downgrade 0067.

## Definition of done
- [x] `tests/unit/fieldwork/test_completion.py`, `spec301completion.test.tsx` and `spec043findings.test.tsx` pass, along with the gate and independence lists; check-fast passes.

## Progress log
- 2026-10-20: built and merged.
