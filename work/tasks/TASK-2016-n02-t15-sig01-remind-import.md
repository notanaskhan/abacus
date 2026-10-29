---
id: TASK-2016
title: N-02-T15 SIG-01 bulk remind and Import signed package
spec: SPEC-381
acceptance_criteria: [AC-1, AC-16]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T15
branch: s15n-n02-t15
created: 2026-10-29
updated: 2026-10-29
---

## Objective
SIG-01 f (bulk remind from the firm's template preview, a person's Send) and r (DF-12 Import
signed package), and the drawer's Remind, in fixture mode (DEC-1057).

Acceptance (backlog row): "On staging Grace imports a signed package that lands under Completed
with its evidence, and the f scenario sends nothing until a human clicks Send."

## Built
- `screens/SIG-01/flows.tsx`: `RemindDialog`, `ImportSheet`.
- `screens/SIG-01/index.tsx`: the check column and selection bar, Remind and Import entry points.
- Fixtures: remind preview and send, `signature_reminder` (DEC-1057), stage and import, clients and
  contacts for r.
- Contract (additive): `RemindIn.template_version`, `template_version_id` optional; client
  regenerated.

## Not built here
- The staging half of the acceptance (record mode live on staging): a person's step (Group C).
- Live remind (N-02-T28).

## Acceptance
| Check | Test |
|---|---|
| f: 3 selected, nothing posts before Send, one send after | `SIG-01 · N-02-T15 > f: …` |
| r: Import waits for the attestation | `SIG-01 · N-02-T15 > r: …` |

In `apps/web/src/screens/SIG-01/SIG-01.test.tsx`.

## Progress log
- 2026-10-29: built (S15 group B). Tests written first, not yet run (end review).
