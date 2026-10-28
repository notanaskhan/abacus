---
id: TASK-1442
title: "Mutation baselines measured and floors set at the baseline (Q-03-T051)"
spec: SPEC-045
acceptance_criteria: [AC-8]  # the floors file is protected (stage 1 refuses a lowered floor); the row's own AC, "Every red module has a recorded floor in the protected file by Fri Apr 2.", is Q-03 §3.3 C1 (no spec AC)
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T051
branch: q03-t051-mutation-floors
created: 2026-10-28
updated: 2026-10-28
---

## Objective
"Mutation baselines per red module measured and floors set at the baseline on S11 (QD-4); M8
targets 85% killed for identity/authz and */compute/, 75% for the other red modules."

## Plan
- Measure: one full `mutation-weekly.yml` run on main (4 shards, mutmut 3.8.0, the
  `[tool.mutmut]` scope unchanged).
- Set each scope's floor in `backend/mutation-thresholds.yaml` to its measured score, rounded
  down. Floors only rise; the `[tool.mutmut]` block and `SCOPES` are untouched.
- Record the baselines as DEC-584. AY approves the floor change before merge (Q-03 §6.2).
- Rollback: revert the PR (lowering a floor is refused by the guard, so a rollback needs AY's
  explicit override).

## Prerequisites (each blocked every shard of an earlier run)
- #551 (DEC-599): tests that read source files are deselected under mutmut (`source_scan`).
- #561: the committed-mutmut-config check is a source scan (shard narrowing changes the file).
- #562: the boundary tests start at the API's fact hold (a worker-boot test left it at 0).
- #564: the bomb test restores Pillow's global pixel limit.
- #565: audit-slot probes register into copies (mutmut runs the suite twice in one process).

## Results (run 40625075584, main 0196043b, 2026-10-28; no scope partial, `not_run` 0)
The score is killed plus timed-out over every mutant generated, so mutants no selected test
reaches ("no tests") count against it.

| Scope | Killed | Timeout | Survived | No tests | Score | Floor | M8 target | Gap |
|---|---|---|---|---|---|---|---|---|
| identity/authz | 1203 | 0 | 548 | 182 | 62.2% | 62 | 85 | 23 |
| kernel/crypto | 442 | 0 | 196 | 189 | 53.4% | 53 | 75 | 22 |
| evidence | 6779 | 19 | 2683 | 21300 | 22.1% | 22 | 75 | 53 |
| ai_gateway | 685 | 1 | 879 | 1783 | 20.5% | 20 | 75 | 55 |
| audit_trail | 431 | 0 | 203 | 2443 | 14.0% | 14 | 75 | 61 |
| kernel/db | 31 | 0 | 58 | 138 | 13.7% | 13 | 75 | 62 |
| kernel/uow | 34 | 0 | 42 | 1541 | 2.1% | 2 | 75 | 73 |
| compute | — | — | — | — | not measured | 0 | 85 | — |

- `compute` (`src/abacus/*/compute/*.py`) matches no file yet; its floor stays 0 until a compute
  package lands and a weekly run measures it.
- Most of the gap in evidence, ai_gateway, audit_trail and kernel/uow is "no tests": code the
  unit, property and acceptance suites never reach (the integration suites, which need
  containers, are outside mutation by design). Q-03-T064 starts on survivors.

## Progress log
- 2026-10-28: four runs aborted on order-dependent and rerun-dependent tests (fixed in
  #561, #562, #564, #565; no assertion changed). Run 40625075584 completed; floors set.
  Mistake made twice: tests that change module-global state without monkeypatch. Candidate lint
  rule: flag assignment to another module's attribute (`Image.MAX_IMAGE_PIXELS = ...`) and
  register_* calls in tests outside a monkeypatched registry.
