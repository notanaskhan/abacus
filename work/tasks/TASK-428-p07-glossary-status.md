---
id: TASK-428
title: Glossary and status-vocabulary rows for P-07 - acceptance, independence, conflicts, intake, import, estate_of; client, invitation, acceptance record, letter record, conflict assessment, NAS and conclusion statuses (P-07-T03)
spec: SPEC-046
acceptance_criteria: [AC-13]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T03
branch: TASK-428-p07-glossary-status
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Both PRs merge, codegen regenerates status data, and banned_patterns accepts the new
identifiers." Add the protected glossary rows and the DF-31 status objects P-07's migrations and
screens (CLI-01, CLI-04, CLI-06, CLI-07, CLI-08) need before they land. Solo edition: one PR,
decided and recorded by the builder (AMENDMENT-solo §2).

## Plan (red zone: docs, generated files and tests only)
- Files: `docs/product/glossary.md`; `docs/product/status-vocabulary.yaml`; generated
  `backend/src/abacus/kernel/_statuses.py` and `packages/ui/src/status.gen.ts` (`make regenerate`,
  never hand-edited); `apps/web/src/status/status.test.ts` (registry counts, with a comment naming
  what was added); `backend/tests/unit/quality/test_glossary_l12.py` (three P-07 cases).
- No migration, registry, flag or matrix edit. No new "Don't use" entries, so the L12 ban list is
  unchanged and no existing identifier can start failing.
- Rollback: revert the commit and rerun `make regenerate`.

## What changed
- **Glossary, New terms: organisations.** `Relationship` gains `estate_of` (estate → decedent's
  entity, DEC-62, CLI-06 c); new rows `Client intake` (`client_intake_drafts`, `client.intake`),
  `Client import` (`client_imports`, `client_import_rows`, `client_import.run`; `import` stays
  banned on its own), `Conflict check` (`conflict_checks`, `conflict_results`,
  `conflict_result_events`), `Screening record` (`screening_records`; human-recorded, not a
  screening result).
- **Glossary, New terms: engagements.** `Acceptance record` (`acceptance_records`, answers, flags,
  decisions; replaces `engagement_acceptance`, which is not banned because it is still in code until
  P-07-T59), `Acceptance condition`, `Independence conclusion`, `NAS evaluation`, `Independence
  breach`.
- **Status vocabulary (+7 objects, +27 codes).** `client` (Prospect · Active · Inactive · Former,
  DEC-62; no pill designed, `variant: null`); `invitation` (Not invited · "Invite pending · expires
  {date}" with portal pill "Invited" · Active · Locked · "Deactivated {date}"; DF-31, CLI-01/04,
  ADM-02 f; codes follow `contacts.portal_status`); `acceptance_record` (Draft · Pre-screening ·
  Awaiting partner · Decided · Declined; CLI-07, DF-06); `letter_record` (Not signed · Letter
  signed; ENG-01 b, ENG-02); `conflict_assessment` (Pending · Clear · "Same family · not adverse" ·
  Not adverse · "Counterparty · {relationship} — review"; CLI-06, CLI-08 c); `nas_evaluation`
  (Pending · Concluded · Not applicable; CLI-08 b); `independence_conclusion` (Independent ·
  Independent with safeguards · Not independent; CLI-08 f). Variants are the pill colours the
  artboards draw; where no pill is drawn the variant is `null`.
- **Counts.** `status.test.ts`: registry objects 61 → 68 and rows 311 → 338, with comments naming
  the additions.

## Decisions taken in the session
- Codes no artboard names are left out rather than given invented words: the `conflict` assessment
  (a confirmed conflict), the invitation record's `accepted`/`revoked`/`expired` (CLI-04 shows the
  contact's portal state, not the invitation row) and the repo's staff-invitation states. P-07-T36
  and the DF-31 follow-up add them with the design's words.
- `invitation` codes follow `contacts.portal_status` (`not_invited`, `invited`, `active`) plus
  `locked` (DEC-35) and `deactivated` (ADM-02), because those are the rows the designs label.
- NAS "Concluded" is `green` (CLI-08 b draws green, not green-tint); "Deactivated" is `tag`
  (#EFEEEB with ink-2, as ADM-02 draws it).

## Collision check
`glossary_bans()` holds `import` but none of the new table names or their first words
(`acceptance`, `independence`, `nas`, `conflict`, `screening`, `client`, `estate`). L12 compares
whole names, singulars and table first words, so `client_imports` passes while `Import` alone fails
(tested).

## Progress log
- 2026-10-23: rows written from P-07 §2.1, §4.2, §4.3, DF-31, DEC-62 and the CLI-01/04/06/07/08,
  ENG-01/02 and ADM-02 handoff specs. Checks: `make regenerate`, `make check-generated`,
  `vitest run src/status/` (62 passed), `pytest` status and glossary suites (793 passed, 20
  xfailed; 13 passed), `banned_patterns`, `validate_docs`, ruff, prettier.
