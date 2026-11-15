---
id: TASK-8036
title: "T-07-T09: fiduciary engine tax/compute/fiduciary.py"
spec: SPEC-656
acceptance_criteria: [AC-5, AC-6, AC-7, AC-11]
risk_zone: amber
status: in-review
branch: t07-t09-fiduciary-engine
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T09
---

## Objective
The pure fiduciary engine: FAI, DNI (§643(a)), expense allocation by character, IDD (§661),
allocation and K-1 (1041) boxes 1, 2a, 2b, retained DNI, the §642(b) exemption, taxable income,
the tie, simple-trust and estate variants, the 65-day window, parameter files, `engine_version`,
`inputs_hash` and a tree projection with clause references.

## Plan (amber)
1. `tax/compute/fiduciary.py` (pure; imports `kernel.numeric` and the package's stamp only).
2. `tax/compute/parameters/fiduciary/ty2025.yaml`, `ty2026.yaml`, `ty2027.yaml` (red files;
   `protected-paths.md` names the directory).
3. `tests/unit/tax/test_t07t09_fiduciary_engine.py`: the three screens' figures and every branch.
Rollback: revert; nothing calls the engine until T-07-T16's computation service.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built. A local run of the engine reproduces TXT-02 a (FAI 430,000; fees 7,500 /
  22,500; DNI 400,000 = 100,000 + 300,000, qualified 240,000; IDD 240,000; Nora 40,000 / 120,000 /
  96,000, Theo 20,000 / 60,000 / 48,000; retained 160,000; taxable income 159,900), TXT-02 d
  (260,000; 61.5% / 38.5%; Theo 25,000 / 75,000 / 60,000; 140,000; 139,900), TXT-01 c (265,000;
  Theo 105,000; 135,000 retained) and the windows Mar 6, 2026 / Mar 6, 2027 / Mar 5, 2028. The
  test suite is not run yet (end pass; coverage measured there).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5023 | Allocation rules; parameters in their own protected directory | no |
