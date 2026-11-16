---
id: TASK-8349
title: "W-01-T15: WB-11 d live: a firm app's client companies through connections, walls applied"
spec: SPEC-659
acceptance_criteria: [AC-17, AC-18, AC-19]
risk_zone: red
status: in-review
branch: w01-t15-client-companies
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T15
---

## Objective
Spec section: SPEC-659 AC-17 to AC-19; WB-11 d. WB-11 d live: a firm app's client companies through connections, walls applied.

## Plan (red)
1. `connections/provider_companies.py`: the catalogue row's provider's live connections (connected, needs attention, needs reauth), newest first, 50 a page (cursor `<connected_at>|<id>`, a malformed one starts from the newest), named by the client entity and who connected it; a walled client is left out and never counted (`identity.api.hidden_clients`); `q` on the client's name.
2. `GET /v1/integrations/{key}/client-companies` (no 501): an app with no connection provider lists nothing.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5335). Lint, pyright and the banned patterns clean; the app imports; regenerated. Partial: `connected_by_label` says (client) for every connector; a firm person who connected on a client's behalf is not told apart yet. Gates and
  tests run once at the S47 end pass (build first, test last).
