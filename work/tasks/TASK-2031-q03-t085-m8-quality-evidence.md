---
id: TASK-2031
title: Q-03-T085 M8 quality evidence (docs/ops/gates/M8-mvp-code-complete.md, quality rows)
spec: SPEC-341
acceptance_criteria: [AC-51]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T085
branch: s15c-q03-t085
created: 2026-10-30
updated: 2026-10-30
---

## Objective
All 55 back-fill items closed (44 back-filled, 7 superseded by merged AC suites, 4 with black-box
suites on their legacy paths from T524 and T525), coverage 95% global and 97% red, mutation floors
recorded, no back-fill defect above SEV3, every finding in the escaped-defect log with its layer;
both founders sign the quality rows on Fri May 28, 2027.

## Plan (amber: written before the code)
- `abacus_tools.quality.m8_evidence`: derives rows Q-1 to Q-6 from `docs/quality/backfill.md`, the
  latest back-fill re-run, `pyproject.toml`, `coverage-exception.toml`, `coverage-thresholds.yaml`,
  `mutation-thresholds.yaml` and `docs/quality/escaped-defects.md`; `--write --sha` refreshes the
  generated block in the gate file; exits 0 only when Q-1 to Q-6 are ready. Q-7 (sign-off) is by
  hand, never derived.
- `docs/ops/gates/M8-mvp-code-complete.md`: the M8 gate file with its sections by owner (quality
  here; the tax go/no-go is F-09-T125's) and the sign-off table.
- SPEC-341 AC-51; tests `backend/tests/unit/quality/test_m8_evidence.py` (run at the end review).
- Rollback: delete the tool and the gate file.

## Derived 2026-10-29 on main (307de40b)
Q-1 ready (55: 44 / 7 / 4), Q-2 ready (44 of 44 green on the Oct 29 re-run), Q-5 ready (16
back-fill defects, none open above SEV3), Q-6 ready (93 findings, each with its layer), Q-4 ready
(every scope has a floor; most are under the M8 targets, shown, not gated: the target is Q-03's
mutation work). **Q-3 not ready:** the DEC-10 coverage exception is live until 2026-12-01 and six
red line floors are under 97 (ai_gateway 82, audit_trail 93, evidence 92, identity/authz 86,
kernel/crypto 87, kernel/uow 92). Closing Q-3 is Q-03-T067's coverage work, not this task's.

## To finish
Re-derive on the pinned SHA on Fri May 28, 2027 (`--write --sha <sha>`); both founders sign when it
exits 0.

## Progress log
- 2026-10-30: tool, gate file, AC and tests built; rows derived on main.
