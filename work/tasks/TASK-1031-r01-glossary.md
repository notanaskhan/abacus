---
id: TASK-1031
title: Glossary rows for R-01 - email templates, drafts, sending domains, suppressions, firm mail policy, follow-up policy, portal settings, drop batch, rule fulfilment and void; UI terms; portal copy bans (R-01-T04)
spec: SPEC-323
acceptance_criteria: [AC-2]
risk_zone: red
status: done
epic: R-01
plan_key: R-01-T04
branch: s7-r01-portal-requests
created: 2026-10-24
updated: 2026-10-24
---

Plan of record: R-01 (docs/plan/epics/R-01.md §4.2, §4.9, §5.7).

## Objective
"The glossary PR merges with notanaskhan's approval and banned_patterns accepts every new
identifier." Add the protected glossary rows R-01's migrations and screens need (R-01 §4.2, §4.9,
§5.7) so T09, T19, T24, T26 and T27 name their tables from the glossary, and record the portal copy
bans. Solo edition: decided and recorded by the builder (AMENDMENT-solo §2).

## Plan (red zone: docs and one lint rule)
- Files: `docs/product/glossary.md`; `backend/src/abacus_tools/quality/banned_patterns.py`;
  `backend/tests/unit/quality/test_glossary_l12.py`.
- No migration, registry, flag or matrix edit; no new "Don't use" entry, so the ban list is
  unchanged.
- **L12 compounds.** The plan's names `email_template_drafts` and `email_suppressions` open with
  `email`, which the Message row bans (DEC-14), and L12 checks a table's first word, so the
  acceptance ("banned_patterns accepts every new identifier") could not hold. The Prompt row already
  allows compounds such as `email_template`; L12 now accepts a table whose whole name a term
  table's "Code name" column names (`glossary_compounds()`). Only term tables count, never the
  legacy-identifier table, so a renamed legacy name stays banned; a compound the glossary does not
  name (`email_threads`) still fails (tested).
- Rollback: revert the commit.

## What changed
- **New terms: requests** Drop batch (`drop_batch_id` on `inbox_files`), Rule fulfilment
  (`created_by_kind = 'rule'`), Fulfilment void (`voided_at`, `voided_by`, `void_reason`), Follow-up
  policy (`follow_up_policies`, DEC-74).
- **New terms: communications** Email template (`email_templates`), Email template version
  (amended: blocks, preheader, one CTA, source, insert-only publish), Email template draft
  (`email_template_drafts`), Sending domain (UI "Sender domain"), Email suppression (address hash
  only), Firm mail policy (the client-mail gate).
- **New terms: portal** Portal settings version (`portal_settings_versions`, `_drafts`), Portal
  client experience, and the UI terms Third-party room, Mark as Done, Ignore and Reminder (UI only;
  code `follow_up`).
- **Copy-level ban** "agent", "AI", "confidence", "task", "issue", a match percentage or a firm
  status word in portal copy or a client email (L2, L7).
- **Tests** five R-01 cases in `test_glossary_l12.py`.

## Progress log
- 2026-10-24: rows written from R-01 §3–§5, DEC-24, DEC-58, DEC-59, DEC-74. Checks:
  `pytest tests/unit/quality/` (all passed), ruff, `banned_patterns` (clean).
