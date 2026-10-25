---
id: TASK-1243
title: Skills setup check - ui-kit-component, build-screen-from-handoff, frontend-feature, design-fidelity-reviewer, docs/screens/_TEMPLATE.md; the handoff text mirror held while the repository is public (F-05-T25)
spec: SPEC-046
acceptance_criteria: [AC-6]
risk_zone: red
status: in-review
epic: F-05
plan_key: F-05-T25
branch: s8b-docs-compliance
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"The protected .claude PR is approved by N and a fresh session ports one kit with specimens using only the skill." (F-05-T25) SPEC-046 is cited only because the task schema needs a spec; F-05's design-system spec has no AC for this row.

## Plan (red zone: `.claude/` and docs only)
- Survey: every named deliverable is already on `main` (SU-09 e7fc75dc, SU-10 215686ef, SU-11 82479440, kit handoffs 8ffa8ab0 and fa5e1057): `.claude/skills/ui-kit-component/`, `.claude/skills/build-screen-from-handoff/`, `.claude/skills/frontend-feature/SKILL.md` (routes screens to the two skills), `.claude/agents/design-fidelity-reviewer.md`, `docs/screens/_TEMPLATE.md`, `docs/design/HANDOFF_VERSION`.
- Finish: the two skills' "Paths that arrive later" lists named eight paths as future; all exist now, so the lists become "Paths this skill relies on" with the stop-and-report rule kept.
- **Not done, on purpose:** the text-only handoff mirror. F-05 §8 (F-01 row) lands it only once the repository is private; the repository is public (agent brief), so it stays outside git and the skills read `$ACCRUED_HANDOFF_DIR`, version-checked against `docs/design/HANDOFF_VERSION`.
- **Rollback:** revert the commit.

## Progress log
- 2026-10-25: checked and finished as above. Approval by the other founder is void under the solo amendment. The "fresh session ports one kit using only the skill" check is evidenced by the C-00 to C-39 ports since S1 through `ui-kit-component` (the kit-handoff commits above), not re-run here.

## Questions for the human
- [ ] When the repository goes private, commit the text-only handoff mirror (or confirm the out-of-git handoff is the permanent arrangement and drop it from the row).

## Handoff
- **Current state:** skills current; mirror held.
- **Exact next step:** the mirror decision above.
