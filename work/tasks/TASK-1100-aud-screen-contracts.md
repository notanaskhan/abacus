---
id: TASK-1100
title: Screen contracts AUD-01, AUD-02, AUD-03 with the glossary and status-vocabulary rows (A-01-T01)
spec: SPEC-330
acceptance_criteria: [AC-1, AC-2]
risk_zone: red
status: done
epic: A-01
plan_key: A-01-T01
branch: s7-a01-audit-wedge
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Every artboard letter is built, fixture-only or recorded as deferred with its owning epic, the link-contract test knows every target, and the glossary and status PR merges with N's approval while codegen emits the phase, archive, rail and export words."

## Plan (red zone, docs only)
- **Files:** `docs/screens/{AUD-01,AUD-02,AUD-03}.md` from `_TEMPLATE.md` and the handoff (README, spec, revision R2; revision wins, DEC-15). 25 artboards: AUD-01 a–i, AUD-02 a–i, AUD-03 a–g, each built, fixture or deferred with its owner.
- **Protected edits:** `docs/product/status-vocabulary.yaml` (new `engagement_export` object; phase, archive and rail words exist as `audit_engagement` and `audit_section`), regenerated `kernel/_statuses.py` and `packages/ui/src/status.gen.ts`; `docs/product/glossary.md` assurance rows.
- **Decision:** DEC-260.
- **Tests:** `tests/acceptance/test_f03_status_vocabulary.py`, the glossary unit tests, `validate_docs`; no manifest change, so `link-contract.test.ts` is unchanged (every outbound link in the contracts is a manifest ID).
- **Rollback:** revert the commit; nothing reads `EngagementExportStatus` yet.

## Progress log
- 2026-10-24: contracts written; every designed link of the three screens in `handoff-links.json` is named with its manifest ID. Codegen emits `EngagementExportStatus`; status-vocabulary acceptance (895 passed, 19 xfailed) and glossary tests (21) pass. N's approval of the protected glossary and status rows is the main session's to collect at merge.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-260 | Persona and clock precedence, deferrals, export words | No |
