---
id: TASK-8547
title: "A-08-T32: AUD-26 live host on the SSARS workspace; AUD-11 MUS option checked"
spec: SPEC-657
acceptance_criteria: [AC-7]
risk_zone: green
status: in-review
branch: a08-t32-aud26-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-18
updated: 2026-11-18
plan_key: A-08-T32
---

## Objective
AUD-26 fixture-to-live on GET /v1/work-items/{id}/ssars; the AUD-11 MUS method option.

## Plan (green)
1. screens/AUD-26/live.tsx: AUD26Live — the rail in the server's order and states (unknown state reads Not started), the engagement's mode and standard, and in review mode the analytics set's statement (AUD-13's Statement, exported)
2. Route /audits/$auditId/ssars; manifest stays planned (DEC-5531: AUD-26's designed links name a client, a return and a run the workspace does not carry)
3. AUD-11 MUS: the method reads 'Monetary unit' with its algorithm line already (A-08-T13); the web has no sample-set create form, so there is no picker to add an option to
4. Tests: live.test.tsx (2)

## Progress log
- `2026-11-18` — Built 2026-11-18 (S49 open rows, round 2). Not done: inquiries, compilation read and preparation preview canvases on live reads; the staging run. Gates and tests run once at the S49 open-rows end pass (build first, test last).
