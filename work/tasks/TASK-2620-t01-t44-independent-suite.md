---
id: TASK-2620
title: T-01-T44 independent AC tests for T-01-T22, T23, T41 and T45
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: T-01
plan_key: T-01-T44
branch: s21-t01-t44
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"The suite is written in notanaskhan's session and passes on main, including a planted
cross-household download that answers 404." (ADR-078.)

## Scope
`backend/tests/unit/tax/test_t01t44_independent.py`: the fake CCH's files conform at engine
versions 1 and 2 (T-01-T22 checks V3) and it refuses a non-synthetic firm in a synthetic
environment; the consents slice foots to C19's six tiles; amounts parse exactly or not at all; an
unseen transcript (the Okafor household) parses and compares to the cent (a one-cent difference
differs; a sum of tenths is exact), a missing return is "not on return", a mismatched year is
refused. `backend/tests/integration/test_t01t44_filed_delivery_independent.py`: through the portal
route, a planted cross-household id and an unknown id both answer 404 with nothing audited; before
the second step 403; after it one `filed_return.downloaded` per download naming no content; a
firm member never downloads through the portal route.
**Note (DEC-1668)**: the plan names notanaskhan's session (ADR-078); under the solo amendment the
suite is written from the contracts and SPEC-501 without reading T-01-T41's tests first, and it
reuses only their seeds.

## Progress log
- 2026-11-01: written; runs at the batch's end review.
