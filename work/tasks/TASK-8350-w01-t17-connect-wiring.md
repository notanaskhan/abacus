---
id: TASK-8350
title: "W-01-T17: Connect flows wired: WB-10 Details… and Enable, WB-11's consent step and the provider's callback"
spec: SPEC-659
acceptance_criteria: [AC-10, AC-11, AC-12, AC-13, AC-14]
risk_zone: red
status: in-review
branch: w01-t17-connect-wiring
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T17
---

## Objective
Spec section: SPEC-659 AC-10 to AC-14; WB-10 interactions; WB-11 b. Connect flows wired: WB-10 Details… and Enable, WB-11's consent step and the provider's callback.

## Plan (red)
1. WB-10: Details… on every listed tile but a coming-soon one opens WB-11 (`ov.WB11`); a personal Enable opens WB-11's consent first; a firm Enable or a Reconnect goes to the provider.
2. WB-11 live: a personal app's consent card (the catalogue's heading, reads and never line, and its own button words, `continue_label`, now on `ConnectConsentOut`, additive) with Cancel and Continue (`connect_personal`, then the provider).
3. `/workbench/connect/callback` (`connect_service.CALLBACK_PATH`): posts the state and code once (a reload never replays), then back to WB-10 with a toast; an expired or replayed state reads as expired; a random idempotency key (never the state).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5336). tsc, eslint and the WB-10, WB-11 and route tests (96) clean; client regenerated. Partial: a fresh-MFA step-up before Enable (the API refuses a stale factor and WB-10 shows the failure); the WB-10 e spinner state stays the button's pending state. Gates and
  tests run once at the S47 end pass (build first, test last).
