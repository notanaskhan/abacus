---
id: TASK-8811
title: "C-02-T27: ADM-08 Ledgers segment live on the T12 frame"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s52-c02t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T27
---

## Objective
ADM-08b renders live for Felix Andersen with both locked rows and Enable writes an audited firm_write_capabilities row.

## Done
- ADM-08 Ledgers reads gl-posting settings (Post as, the firm switch) via the generated client; PostingSwitch row with Enable… Dialog and Turn off; 403 offers ConfirmItsYou
- W1GlPostingSettingsOut gains w1_enabled/w1_released (additive); make generate regenerated packages/api-client (includes C-02-T24's reverse route)
- fixture handlers for gl-posting, enable, disable
- ADM-08 test for the live row
- docs/screens/ADM-08.md deviation recorded

## Progress log
- `2026-11-20` — FE + additive contract; vitest at the end pass.
