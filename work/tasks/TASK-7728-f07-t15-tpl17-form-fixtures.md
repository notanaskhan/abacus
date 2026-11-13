---
id: TASK-7728
title: F-07-T15 TPL-17 form-page fixtures
plan_key: F-07-T15
spec: SPEC-652
acceptance_criteria: [AC-6]  # byte-deterministic on rerun; manifest values foot to Schedule K; no tenant or database written
risk_zone: green
status: in-review
branch: f07-t15-tpl17-form-fixtures
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
A test-only specimen face set (1065 p1, Sch K pp4–5, Sch L/M-1/M-2 p6, K-1 Jonah Feld, K-1 Pell
Street II) rendered once through the C11 renderer, rasterised by the evidence preview path, with a
field manifest (rect, label, value, match_id, diagnostic).

## Plan
- `backend/src/abacus_tools/specimens/{__init__,form_faces,render_form_fixtures}.py` (new).
- `backend/tests/golden_render/form_fixtures.sh` (new) and `make form-fixtures`.
- `packages/ui/src/specimens/fixtures/tpl-17/` (generated PNGs and manifest).
- Tests: `backend/tests/unit/tools/test_f07t15_form_faces.py` (pure).
- Rollback: revert; nothing reads the fixtures until FormRendererLayout (F-07-T18).

## Partial
- M-1 has no values on the drafted page 6 (the spec's page 6 states are M-2's); the face carries
  Schedule L line 21 and M-2.

## Progress log
- 2026-11-13: built; ruff and pyright clean; `make form-fixtures` run: two containers agreed byte
  for byte; six pages and a 54-field manifest committed (manifest sha256 3e9e0055…). Unit tests
  written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4731 | faces as data, C11 regions for rects, image-bound generation, tooling location | no |
