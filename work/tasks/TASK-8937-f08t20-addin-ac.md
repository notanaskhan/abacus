---
id: TASK-8937
title: "F-08-T20: Independent AC tests for the add-in pane"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-f08t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: F-08-T20
---

## Objective
Independent AC tests for the add-in pane (ADR-078). Acceptance: Tests prove no sign-off fires without a named human click, offline disables Sign-off, Changes equals the changed cells, and signed-out copy comes from branding data.

## Done
- packages/ui/src/addin/addin-pane.ac.test.tsx from F-08 §3 E1/E2 only (7 tests): no sign-off without a click, Sign off again only opens the dialog, offline disables Sign-off (bar, queued, Last synced), Changes lists exactly the changed cells, signed-out copy takes the firm name from branding, one primary per card, host chrome not on the main entry

## Progress log
- `2026-11-23` — 2026-11-23: written in a clean read of the epic (ADR-078); one test over-read 'named human click' as a name in every label; triaged as test error (the epic names the person only in 'Sign off again as …') and corrected. 7 pass.
