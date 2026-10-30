---
id: TASK-2303
title: P-11-T06 report templates as database content
spec: SPEC-520
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T06
branch: s18-p11-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Report templates as firm content: `report_templates`, insert-only versions and publications;
DocBlock validation with the clause library and declared variables; import with dry run;
human-only publish with fresh MFA; audit events. Acceptance (row): a bundle imports as a draft
version with a validation report, markup, unknown variables and unknown layouts are rejected, and
publication is human-only, audited and never done by a migration or constant.

## Plan
- Migration 0460 (on 0430): the three tables in methodology, forced RLS, insert-only triggers,
  `published` needs `mfa_at`; registry, models, tenant-isolation list.
- `methodology/report_templates.py`: import (next version, same content stores nothing), publish
  (human, four eyes, `already_published`), current version computed, reads; exported through
  `methodology.api`.
- `reporting/templates.py`: validation by path and the four live routes in `contract.py`
  (late imports: templates imports contract's models). Preview stays 501 until P-11-T07.
- Matrix unchanged (P-11-T03 set it); `fresh-mfa-actions.yaml` gains `report_template.publish`.
- `make generate` (501 dropped from four routes); error catalogue regenerated.
- Tests: `tests/unit/reporting/test_p11t06_template_import.py`,
  `tests/integration/test_p11t06_report_templates_schema.py`; C11 stub tests split live/stub.
- Rollback: revert; 0460 downgrade drops the tables.

## Per AC
| AC | Evidence |
|---|---|
| AC-1 | `test_ac1_*`: report by path, unknown variable/layout, clause conflicts, too large, warnings; integration: RLS, no inserted rows |
| AC-2 | `test_ac2_*`: tags, schemes, `www.`, `{{`, `{%`, `${` in body, tables, clauses, sample data |
| AC-3 | `test_ac3_*`: agent/system refused and audited, client 404, four eyes, publication CHECK needs `mfa_at` |
| AC-4 | `test_ac4_*`: current version computed, republish rolls back; versions and publications insert-only for every role |
| AC-5 | `test_ac5_*`: no `INSERT INTO report_template_versions` in source or migration |

## Progress log
- `2026-10-30` — built (DEC-1350). Tests written, not yet run (S18 end review).

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** P-11-T07 renderer core; the SAMPLE preview route goes live with it.
