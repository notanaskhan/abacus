---
id: TASK-1736
title: N-02-T10 Signatures fixtures and scenarios
spec: SPEC-381
acceptance_criteria: [AC-4]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T10
branch: s14-n02-t10
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The SIG-01 seed, handlers and scenarios. Acceptance (backlog row): "Every scenario loads in fixture
mode and the seed tests foot 8 + 5 + 4 = 17 and 6,500 + 12,000 = 18,500."

## Plan
- `fixtures/seed/signatures.ts`, `fixtures/handlers/signatures.ts` (SIG01_SCENARIOS a–g, r).
- C7 `EnvelopeListRow` additive fields; `make regenerate`. DEC-826 (SIG-02, POR-06, ENG-04
  scenarios with their screens).
- `fixtures/signatures.foot.test.ts`.

## Progress log
- `2026-10-28` — Built. tsc, eslint, prettier, ruff, pyright clean. Tests written, not run.

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** N-02-T11 (SIG-01 hub on these scenarios).
