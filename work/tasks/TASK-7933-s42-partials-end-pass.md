---
id: TASK-7933
title: "S42 partials end pass: gates, tests, security review and one fix round"
plan_key: Q-03-T285
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s42-partials-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The S42 partials round's end pass over #1932–#1941: stage-1 gates, the full backend unit suite, ui and web vitest, a security review of the red rows, one fix round.

## Done
- Gates: ruff, format, banned patterns (the eval grader now reads tax through `tax.api`), validate_docs (task titles quoted, SPEC-654 AC ids), pyright: all clean after the round; generated files and the single migration head (0871) clean.
- Backend unit: 48,270 passed; the only non-passes are the local-only libgobject classification and fs_render tests (green in CI) and the two gate tests fixed here. ui 1,421/1,421; web 4,020/4,021, the one failure (gallery seed, a 1 s findByText under the full run's load) passes alone.
- Security review (Medium, fixed; DEC-4928): the free-text fix's model call named no §7216 subject and the gateway checks consents only for named subjects; it now names `entity_return_subjects(tenant, return_id)`, failing closed for an unknown return. Test added.
- Low, accepted: `briefing.today`'s call names no subject (dispatch's `capability_ready` refuses consent_7216 first; per-engagement subjects to I-02-T22's threat-model pass); WB-02's AUD-09 link takes the audit id from the model's entity_ref (the route authorises; a hostile id 404s).

## Partial
- I-02-T22: name each engagement's TRI subjects on the briefing call (defence in depth).
- Closed by S43 (2026-11-14, main 322ca3310): I-02-T22 (#1986): the briefing call names its TRI subjects (DEC-4945).

## Progress log
- 2026-11-13: built in the S42 partials round; tests written, run at the partials end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4928 Every tax model call names its §7216 subjects | The gateway's consent check runs only for named subjects | no |
