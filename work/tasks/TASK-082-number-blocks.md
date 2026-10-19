---
id: TASK-082
title: Number blocks and reservation forms — validate_docs refuses out-of-block and duplicate ids, new ADRs name GitHub handles (epic F-01-T10)
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: red
status: done
branch: task-082-number-blocks
worktree:
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Two founders (or two sessions) never mint the same ADR, SPEC or TASK number, and new ADRs say which founder decided (epic F-01-T10).

## Scope
**In**
- `validate_docs.py`: number blocks after the legacy ids (ADR ≤ 115, SPEC ≤ 036, TASK ≤ 076 untouched): ADR 116–199 notanaskhan, 200–299 ayushkbhatia; SPEC 037–099 / 100–199; TASK 077–499 / 500–999. An id outside every block fails; duplicate ids already fail. ADRs ≥ 116 must list GitHub handles as `deciders` (bare, comma-separated or a list; `@` allowed when quoted).
- ADR-131 and ADR-132 (accepted 2026-10-19 with `deciders: Founder`, immutable) are grandfathered by name in `LEGACY_DECIDERS`.
- `.github/ISSUE_TEMPLATE/reserve-{adr,spec,task,dec}.yml`: reservation forms, title `KIND-NNN: <title>`, block owner, owning epic.
- `docs/adr/_TEMPLATE.md`: deciders hint names the handles.

**Out**
- "Red-zone ADRs list both handles" (P-02): the founder waived the other founder's approval on 2026-10-19; record the rule, if wanted, in the two-founder governance ADR first.
- The TASK-076 reuse rule: TASK-076 now exists (SPEC-036 part 2), so the duplicate check covers it.

## Plan
Approved by founder (2026-10-19, auto mode): paths `backend/src/abacus_tools/quality/validate_docs.py`, `backend/tests/unit/quality/test_validate_docs.py`, `.github/ISSUE_TEMPLATE/**`; approval file `work/approvals/TASK-082.yaml`, expires 2026-10-26.

## Definition of done
- [x] `test_validate_docs.py` passes (76, 36 new); the repo itself validates; `make check-fast` passes.
- [ ] CI green on the PR.

## Progress log
- 2026-10-19: validator, tests, forms and template.

## Gotchas and discoveries
- The `spec005` session's uncommitted `TASK-077-fieldwork-selection.md` will now fail `validate_docs` as a duplicate of TASK-077; it needs a free number in 083–499.

## Questions for the human
- None.

## Handoff
Merge after CI; delete `work/approvals/TASK-082.yaml`. F-01's S0 tasks for notanaskhan are then done except T04 (two-founder hook, superseded by the founder's waiver).
