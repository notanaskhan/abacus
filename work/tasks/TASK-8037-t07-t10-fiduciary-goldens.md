---
id: TASK-8037
title: "T-07-T10: ADR-078 goldens and properties for the fiduciary engine"
spec: SPEC-656
acceptance_criteria: [AC-5, AC-6, AC-7, AC-9, AC-11]
risk_zone: amber
status: in-review
branch: t07-t10-fiduciary-goldens
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T10
---

## Objective
The fiduciary engine's goldens, transcribed from the epic and the handoff (each citing its
screen and state), Hypothesis properties (footing, conservation, idempotence) and the CPA review
packet.

## Plan
1. [x] `tests/golden/fiduciary/calloway_ty2025.yaml`: base, theo_changed, principal_invaded,
   by_character, simple_trust, gains_in_dni, windows.
2. [x] `tests/golden/fiduciary/test_t07t10_calloway_goldens.py`: the goldens and three properties.
3. [x] `docs/quality/fiduciary-cpa-review-packet.md`.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built. Solo edition: the "transcribed by N" independence is one builder's
  (AMENDMENT-solo); the YAML was written from the epic's figures, not read back from the engine.
  Not run (end pass).
- **Partial (human).** The packet's send to the tax CPA (due Fri Jul 21, 2028) and the CPA's
  sign-off are a person's.
