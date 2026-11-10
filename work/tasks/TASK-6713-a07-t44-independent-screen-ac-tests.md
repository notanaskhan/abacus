---
id: TASK-6713
title: "A-07-T44: independent AC tests for the A-07 screens: no gate control on agent-owned elements, final verbs never optimistic, disabled controls say why, read-only variants, no delete after lock"
spec: SPEC-644
acceptance_criteria: [AC-37]
risk_zone: green
status: in-review
branch: s35-a07-t44
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T44
---

## Objective
Tests fail if any final verb renders as done before the server confirms it.

## Plan
`apps/web/src/screens/a07-independent.ac.test.tsx` (ADR-078 solo independence, DEC-3127): written
from A-07 §5 and INV-1, not from each screen's suite. Every frame of AUD-22, AUD-23, AUD-24 and
AUD-25: no final-verb control inside a `data-actor="agent"` element; disabled final controls carry
words beside them; non-partner and no-right variants disable Release, Approve & send and Lock;
Release and Lock call the host and the canvas does not show the act done; no delete or remove
control after lock.

## Partial
- AUD-18, AUD-19 and AUD-21 are data-driven (live or scenario hosts); their concur, completion and
  approve-and-send rules are in their own suites; this file covers the four frame-driven screens.
- The step-up itself is the host's (SHL-12, the MFA dialog); these screens only call it.

## Progress log
- `2026-11-10` — Written; run at the end pass.
