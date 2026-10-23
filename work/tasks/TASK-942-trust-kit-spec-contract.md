---
id: TASK-942
title: SPEC-322 Trust kit v1, the C4 contract doc c04-citations-viewer.md, the C4 register row and the glossary additions (P-03-T01)
spec: SPEC-322
acceptance_criteria: [AC-41, AC-42]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T01
branch: p03-t01-t27-trust-kit-docs
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"SPEC, contract doc and glossary PR merge with ACs keyed to SHL-07a-e and SHL-08a-f/h, cite ADR P-48, ADR-066, ADR-004 and ADR-110." (Solo edition: no approval file.)

## Plan (red zone, docs only)
- **Files:**
  - `docs/specs/SPEC-322-trust-kit-v1.md` (new): AC-1 to AC-42, each mapped to its P-03 §3 AC and its SHL-07 or SHL-08 letter;
  - `docs/contracts/c04-citations-viewer.md` (new): every P-03 §4.3 route, its matrix action, flag, refusal codes, audit event names and the reserved 501;
  - `docs/contracts/README.md` (C4 row: file, status stub);
  - `docs/product/glossary.md`: Citation refined, and new rows for Citation event, Evidence page / word layer, PII region, PII reveal and Evidence derivation;
  - `docs/product/decision-log.md` (DEC-148).
- **Not edited:** `docs/product/status-vocabulary.yaml`. Per the coordinator, the C4 stub PR (P-03-T02) adds the citation, viewer and unlock words there, because the vocabulary test is tied to its route models. The SPEC and contract reference them.
- **Migrations, registry, flags, code:** none. The models, routes, matrix and flags are P-03-T02, and the migration is P-03-T04.
- **Tests:** `validate_docs`, `secrets_scan`, `scope_guards`, `make check-generated`. The contract is proven by P-03-T03 (`backend/tests/contracts/c04_citations_viewer/`).
- **Rollback:** revert the commit.

## Progress log
- 2026-10-23: written in parallel with the C4 stub. The contract doc keeps to P-03 §4.3 and says "shapes per P-03 §4.3" where the stub's class names or facts keys may differ. The stub's state codes were taken as given: `CitationV2Out.state` has `valid`, `moved`, `broken` and `relinked`; `ViewerManifestOut.status` has `processing`, `ready`, `password_protected`, `unreadable` and `not_previewable`; `EvidenceUnlockOut.status` has `ready` and `wrong_password`. The register's planned file name `citation-v2.md` became `c04-citations-viewer.md`, the epic's name. P-03 §11.2 OQ-1 to OQ-8 were decided with the plan's recommendations (DEC-148), so SPEC-322 has no open question and is `approved`. TASK-941's file joins this commit because it names SPEC-322.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-148 | contract file name; one flag per route family; unreadable reads "Can't preview"; OQ-1 to OQ-8 | no |
