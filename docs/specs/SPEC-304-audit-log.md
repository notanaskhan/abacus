---
id: SPEC-304
title: "Audit log explorer: the firm's audit trail, newest first, filtered and paged, for firm admins, the practice leader and the quality partner"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-007, ADR-018]
related_specs: []
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
A read-only explorer over `audit_events`, which hold identifiers and references only (ADR-007). It sits under Firm settings › Security › Audit log.

## 2. Acceptance criteria
- **AC-1** `GET /v1/firm/audit-events` returns up to 100 events, newest first (by `seq`), with `next_before` for the next page.
  - The kernel answers, as the trail's owner (`audit_page`), with static SQL.
  - Names are resolved for people. Agents, the system and support show their identifier.
- **AC-2** Filters, all optional: action, actor kind, actor id, target type, target id, from and to (whole days). A row's target narrows the explorer to that target's history.
- **AC-3** `GET /v1/firm/audit-events/facets` lists the distinct actions and target types for the filters.
- **AC-4** `audit.read` is for firm admins, the practice leader and the quality partner. Others are refused with 403, and the page explains why.
- **AC-5** "Download CSV" exports the rows shown.

## 3. Out of scope
- An engagement filter: events carry no engagement column.
- Per-tenant hash chaining (ADR-007 follow-up).
- Server-side exports.
- Retention views.
