---
id: TASK-8614
title: "Q-05-T32: Amendment to P-14 (ADR-179) on the destruction mechanism and synthetic-tenant retention (draft)"
spec: SPEC-711
acceptance_criteria: [AC-25, AC-26]
risk_zone: red
status: in-review
branch: q05-t32-p14-amendment
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: Q-05-T32
---

## Objective
Spec section: docs/plan/epics/Q-05.md §0.1, §11.2 OQ-1 and OQ-3. Amend P-14 (ADR-179): version deletion on primary and replica after retain-until through a destruction-only role, DB tombstones, derived-store purge, a certificate with the 35-day backup statement; crypto-shred stays offboarding; synthetic-tenant minimum retention outside production.

## Plan (red)
1. An Amendment section in ADR-179 (the ADR-152 in-file amendment precedent), status proposed, with the reason (ADR-104 embeds the wrapped key in the object), the mechanism, the certificate, the offboarding boundary and OQ-3.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5614). Partial by design: the acceptance needs counsel's acknowledgement, which is human; the amendment is drafted and proposed, and Q-05-T14/T15 wait for its acceptance. Gates and tests run once at the S50 end pass (build first, test last).
