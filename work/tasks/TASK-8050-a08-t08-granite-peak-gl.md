---
id: TASK-8050
title: "A-08-T08: Brightwater Hale fieldwork content — Granite Peak FY2026 GL generator (part)"
spec: SPEC-657
acceptance_criteria: [AC-0.8, AC-1.1, AC-1.2]
risk_zone: amber
status: in-review
branch: a08-t08-granite-peak-gl
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T08
---

## Objective
The constrained Granite Peak GL that the JE test reads: 18,426 entries, 412,903 lines, 214
accounts tied, synthetic posting users with roles, JE-26-17994 and JE-26-17950, the holiday set.

## Plan (amber: written before the build)
1. `brightwater_hale/granite_peak_gl.py`: entries by criterion combination, balanced lines,
   NetSuite CSV with JE columns, the Jun 30 TB, role map, criteria and holiday set as scenario data.
2. `tests/golden/scenario/test_a08t08_granite_peak_gl.py`: counts, exact hits, 34 ≥ 61, named
   entries, the tie through `gl_parse` + `validate_gl`, the import cap.
Rollback: revert; nothing loads it yet.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029); plan above written before building.
- `2026-11-15` — Built (DEC-5035). A one-off run: 18,426 / 412,903; hits 142 · 38 · 61 · 17 · 9 →
  236; 34 ≥ 61; tie 214 of 214, failure None; 45.5 MB. Tests run at the end pass.
- **Partial:** support PDFs, AR population and confirmations, Lakeshore, Fenwick, Juniper & Oak,
  the firm content import and `make fixtures` wait on the services that load them (T12–T22).
