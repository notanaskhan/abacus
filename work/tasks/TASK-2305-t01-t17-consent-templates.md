---
id: TASK-2305
title: T-01-T17 consent templates on P-11's report templates
spec: SPEC-501
acceptance_criteria: [AC-28, AC-29, AC-30, AC-31]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T17
branch: s18-t01-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Kind `consent_7216` with purpose, mandatory-statement version, counsel-approval attestation and
recipients source; import with dry run through the template import route; publish by a partner
with fresh MFA; recipients rendered from the provider-terms register at render time (DF-16);
deprecate; content as database rows only. Acceptance (row): a template naming Anthropic as a
recipient is refused, the rendered consent names Amazon Web Services (Bedrock) from the register,
and no consent text exists in code.

## Plan (red: written before the build)
- Stacked on #816 (P-11-T06) and #818 (P-11-T07); merges after them.
- Migration 0461 (on 0460): `report_template_consent_terms` insert-only, one per version.
- C11 v1.1 additive: `ConsentTermsIn/Out`, `TemplateImportIn.consent`, `ReportTemplateVersionOut.consent`,
  three import codes, `deprecate` route; frozen v1 snapshot still passes (additions only).
- `reporting/templates.py` consent rules; `reporting/consent.py` register recipients and named
  parties; `methodology/report_templates.py` terms storage, family-aware publisher, deprecate.
- Matrix unchanged (C19's `consent_template.publish` already partner + fresh MFA).
- Tests: `tests/unit/reporting/test_t01t17_consent_templates.py`; C11 stub lists gain deprecate.
- Rollback: revert; 0461 downgrade drops the table.

## Per AC
| AC | Evidence |
|---|---|
| AC-28 | `test_ac28_*` (Anthropic/OpenAI/AWS in text refused, recipient block once, terms/family/layout) |
| AC-29 | `test_ac29_*` (register line, unavailable when no covering entry, rendered HTML names AWS (Bedrock)) |
| AC-30 | `test_ac30_*`; service: `_publisher` picks `consent_template.publish`, `ConsentTermsMissing`, `NotCurrent` |
| AC-31 | `test_ac31_*` (no consent wording in src or migrations) |

## Progress log
- `2026-10-30` — built (DEC-1352). Tests written, not yet run (S18 end review).

## Handoff
- **Current state:** built, PR open, held for the S18 batch (merge after #816 and #818).
- **Exact next step:** T-01-T10 consent capture renders from the published consent template.
