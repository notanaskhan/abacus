---
id: TASK-8754
title: "G-04-T21: Journey E2E, screen E2E and parity: j01 1 and A4, j14 5, j27 2 (plan and usage) with INV-1..5 and axe; plt-01, adm-14 and shl-05 specs; lock PLT-01 a-d, f, g, ADM-14 a-f and SHL-05 a-f, d' at Tier C; report PLT-01 e at Tier C from fixture mode; Tier D"
spec: SPEC-681
acceptance_criteria: [AC-15]  # the support-request sheet has no approve control (PLT-01d spec); the row's acceptance is under Objective
risk_zone: green
status: in-review
branch: s51-g04t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: G-04-T21
---

## Objective
The named Playwright tests pass with INV-1..5, axe finds no serious or critical issue, and parity.json shows the three screens locked at Tier C.

## Plan (green)
1. Screen specs `e2e/screens/PLT-01.spec.ts`, `ADM-14.spec.ts`, `SHL-05.spec.ts`: every artboard from the gallery at 1440×900 DPR 2 with axe at zero serious or critical, plus PLT-01d no approve control, PLT-01g toast, ADM-14a 14,920 of 20,000, ADM-14e read-only banner, SHL-05c grant and Revoke, SHL-05e Needs attention.
2. Journeys: J01 'j01 1' (Rowan on PLT-01) and 'j01 A4' (ADM-14a), J14 'j14 5' (SHL-05 a → d′ → e → c), j27 'j27 2 (plan & usage)' plus the INS-02 hop as test.fixme until I-03; staging and canary fixme until the console issuer and support.panel_v2 are on staging.
3. Gallery: ADM-14 artboard registered (a–f on its scenarios), PLT-01 wrapped in data-artboard; screen-scenarios gains ADM-14; persona rowan-achebe.
4. Parity: `## Parity` tables lock PLT-01 a–d, f, g, ADM-14 a–f and SHL-05 a–f, d′ at Tier C; PLT-01 e reported; host rows Tier D; PLT-01 and ADM-14 join BUILT_PLANNED so the report measures them.
5. Rollback: revert the PR; tests and docs only plus the gallery registration.

## Progress log
- `2026-11-20` — Built, stacked on #2392. Ran locally on this worktree's own port (ABACUS_PORT_OFFSET=100; 5173 belongs to another checkout): 26 screen tests pass with axe clean; the five new journey tests pass in the fixture project with axe and INV-1..5 (the INS-02 hop is fixme). screen-scenarios and parity unit tests pass, tsc and eslint clean. Not done: staging with real auth (no ABACUS_STAGING_URL here; G-04-T14's staff issuer and Rowan's platform seat are not provisioned on staging), and parity diffs (handoff baselines absent), so parity.json lists the rows locked but unmeasured. j01 1 asserts the tenant row (US, 46 of 46, the service lines) and the created toast on the fixture console, not the provisioning write or tenant.provisioned, which need the live workflow. Gates and tests run once at the S51 end pass (build first, test last).
