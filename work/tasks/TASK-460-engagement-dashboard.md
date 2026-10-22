---
id: TASK-460
title: "K-04 ENG-12 first slice: the engagement dashboard (gates, tiles, next up)"
spec: SPEC-317
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: done
branch: task-346-dashboard
worktree: spec005
created: 2026-10-22
updated: 2026-10-22
---

## Plan keys
K-04-T33, K-04-T40 (partial). Recorded in docs/plan/status/status-verified.csv (TASK-901).

## Plan
- **Engagements:** the `register_progress_source` / `progress_of` slot.
- **Fieldwork:** the `progress` source, plus `engagement_progress_rows` (LIST_EXEMPT).
- **Assurance:** `dashboard.py`, the `dashboard_router` (`GET …/dashboard`) and the matrix action `dashboard.read`.
- **Exports:** `review.api.notes_for` and `workpapers.api.checks_for`.
- **Web:** `legacy/EngagementDashboard.tsx`, plus the route and tab.

## Notes
- Numbered TASK-460 to stay clear of the other stream, which is past TASK-398.
- The other stream moved every screen to `apps/web/src/legacy` (F-05-T23); this screen lives there too.
- `test_preregistration`: tax, closes and notices now hold subtype tables (F-03-T22, migration 0089), so they join LANDED. The test had been failing on main.
- Local DB: migrations 0080–0089 needed the new `abacus_ops` role. The idempotent `bootstrap.sql` and `bootstrap-local.sql` were re-run, then the database was migrated to head.

## Progress log
- Dev smoke test, as the dev engagement's partner:
  - gates G1–G3 met, G5 not;
  - accounts mapped 32 of 32;
  - requests received 0 of 2;
  - "next up" empty, which is correct: the partner doesn't prepare, and nothing awaits review.

## Definition of done
- [x] `tests/unit/assurance` and the API and independence tests pass.
- [x] spec317dashboard (3) passes.
- [x] check-fast passes.
