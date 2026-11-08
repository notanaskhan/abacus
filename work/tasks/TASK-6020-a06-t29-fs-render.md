---
id: TASK-6020
title: "A-06-T29 the FS draft render: a code-composed financial_statements document, DRAFT mark, AR-C 70 legend"
spec: SPEC-000  # row (A-06-T29)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T29
branch: s29n-a06-t29-fs-render
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-08
updated: 2026-11-08
---

## Objective
The row's render part: "Two renders of Northwind v3 are byte-identical, the client copy carries
DRAFT and no checklist or sources." TASK-5123 built the workbooks and the management-approval
event; send-draft waits for R-02's C10 and C18 services (S31).

## Plan
- **Decision (DEC-2615):** the FS document is composed by code from the sealed statement version,
  not from a firm template: its figures are code's (ADR-050), its notes are the version's own
  rendered note templates, and nothing else may appear on a client copy (AUD-20d).
- C11 (`reporting`, additive): layout `financial_statements` (flow, no letterhead); a kind may
  register a `body_provider`, so it renders with no template version and seals its body in the
  snapshot (`body`); compose and the render job read a sealed body; regenerate re-asks the
  provider. Existing snapshots and hashes are unchanged (no `body` key).
- `reporting/fs_render.py`: the `fs_package` kind and its body: entity, statement title and
  period headings, one table per statement (decimal strings formatted by code, negatives in
  parentheses, no "$"), the notes; a preparation engagement (AR-C 70) adds the legend "No
  assurance is provided." on every page (R-19). No citation, source, checklist or agent text.
  `render_statement_draft(ctx, version_id)`: `statement.send_draft`, a DRAFT render in the
  caller's unit of work, for send-draft to call once C10 lands.
- `engagements.engagement_label` gains the entity name and the fiscal period end (additive).
- Tests: composition is deterministic and carries no sources (unit); HTML identical on rerun;
  PDF bytes identical (golden render, image-bound); the AR-C 70 legend on a preparation
  engagement only; C11 rules for body kinds. No migration.
- Rollback: revert; no data written outside generated documents.

## Progress log
- 2026-11-08: plan written; building.
- 2026-11-08: built. Unit `test_a06t29_fs_render` 15 passed; reporting unit suite 119 passed;
  golden render (image) 67 passed with the three FS checks (byte-identical, DRAFT on every page,
  the AR-C 70 legend on every page). The integration run on the Brightwater completion slice
  found two real gaps, both fixed: the version CHECK on `layout_key` (migration 0701), and the
  captions (the draft engine writes `financial_position` and `activities`, so a plan's captions
  follow the engagement type, `ebp_audit`). Kept C11's template contract unchanged: the new
  layout is a kind layout only (`KindLayout`), never a template's `LayoutKey`.

## Decisions made during this task
DEC-2615
