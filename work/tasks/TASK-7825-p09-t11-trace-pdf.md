---
id: TASK-7825
title: "P-09-T11 rest: the trace export's PDF"
spec: SPEC-648  # AC-3 (trace exports)
acceptance_criteria: [AC-3]  # byte-identical exports, audited with the person and sha256, fresh MFA
risk_zone: amber  # an additive contract field and a renderer call
status: in-review
branch: lo39-p09-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: P-09-T11
---

## Objective
P-09-T11's JSON export with its signed manifest is built (TASK-6518, DEC-3118); the PDF half was
not (no C11 layout, no local WeasyPrint).

## Plan
- `agents/trace_pdf.py`: DocBlocks from the export's canonical JSON body; C11's `run_export`
  layout via `reporting.api.render_isolated`; refusals and missing libraries are 503
  `renderer_unavailable`.
- `runs.export_trace(ctx, run_id, format)`: `pdf` renders; the manifest adds `format` and
  `source_sha256`; `sha256` and the audit event name the delivered bytes.
- Route and contract: `format` takes `pdf`; `media_type`, `content_encoding`, `source_sha256`
  (additive); `make generate`.
- WB-09's TraceDrawer: "Download PDF" enabled; the download decodes base64.
- Tests: `tests/unit/agents/test_p09t11_trace_pdf.py` (7; the renderer replaced by a stand-in:
  this Mac has no WeasyPrint libraries; CI renders).
- Rollback: revert; JSON exports are unchanged byte for byte.

## Progress log
- 2026-11-13: built; unit tests pass, ruff, pyright and import contracts clean, client
  regenerated, web tsc and eslint clean.

## Decisions made during this task
DEC-4820.
