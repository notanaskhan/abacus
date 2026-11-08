---
id: TASK-6104
title: "P-10-T13 route parity for tools and documents; loop specs refused on a route without it"
spec: SPEC-000  # row (P-10-T13)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T13
branch: s30-p10-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ADR-234 §7: parity checks for tools and documents per catalog model, committed reports, and loop-shaped specs ineligible on a route without tool parity.

## Plan
- `routes/parity.py` (protected): `ModelParity.tools/documents`, `ParityReport.tool_parity`, `read_report` for old and new reports, `_tools` and `_documents` probes through seam v2's mapping, a hand-built synthetic one-page PDF.
- `kernel/config.py`: `ParityRecord.tool_parity` (default false).
- `routes/__init__.py`: `route_enabled_for(route, shape)` and `loop_routes(routes)`.
- `abacus_tools/route_parity.py` prints `tool_parity`; `docs/operations/route-parity/README.md`; gateway README.
- Tests: `tests/unit/ai_gateway/test_p10t13_route_parity_tools.py`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
DEC-2702
