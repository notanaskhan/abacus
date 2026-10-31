---
id: TASK-2408
title: P-11-T08 RenderWorkflow and generated-document service (C11 v1)
spec: SPEC-000  # the backlog row; C11 (docs/contracts/c11-renderer.md) and P-11 §4
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T08
branch: s19-p11-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The generated-document service: register_document_kind, whitelisted variables, sealed snapshot
and content hash, versions and render jobs, final render only with a verified human approval,
lock, and the out-of-date consumer; audit and outbox events.

Acceptance: "A missing variable refuses with missing_variable instead of a blank, an
agent-requested render is always a draft, a final render without a matching human approval is
refused, and a source change marks the document out of date within one relay cycle."

## Plan (amber)
Files: `reporting/documents.py` (new), `reporting/api.py` (render, render_final, lock,
generated_document, SUBSCRIPTIONS, WORKFLOWS/ACTIVITIES), `methodology/report_templates.py` +
`methodology/api.py` (`report_template_variable_keys`), `tests/contracts/c11_renderer/test_c11_stubs.py`
(the tx argument), `tests/integration/test_p11t08_render_service.py`, DEC-1456.
Migrations: none (0430 has the tables). Registry and flags: none. Rollback: revert; nothing calls
`render` yet. Deferred: the render job's workflow and activity to P-11-T09 (DEC-1456).

## Progress log
- `2026-10-30` — Built on `s19-p11-t08` (build-only; tests run at the end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1456 | tx per C11, whitelist and hash, final checks, live subscriptions, workflow with T09 | no |
