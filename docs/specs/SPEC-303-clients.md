---
id: SPEC-303
title: "Clients index (CLI-01) and client record (CLI-02), joined from the engagements a person can see"
status: approved
owner: founder
risk_zone: green
related_adrs: [ADR-020, ADR-027]
related_specs: [SPEC-025, SPEC-302]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
A first slice of the plan's CLI-01 and CLI-02, with no new tables or permissions. The screen groups the engagements the person can already list by client and entity. A client therefore appears only through a visible engagement, so walls and independence hold.

Engagement summaries now carry `client_id` and `client_entity_id`.

## 2. Acceptance criteria
- **AC-1** Grouping is pure code, in `groupClients`:
  - client, then entity, then engagements, newest year end first;
  - per client: the active count, the overdue client items (from `/v1/firm/waiting/overdue`), and the latest year end.
- **AC-2** `/clients` (a toolbar "Clients" link) shows a searchable table: client, active engagements, overdue client items, latest year end.
  - It filters to "With active work" by default; "All" shows every client.
  - A row opens the record.
- **AC-3** `/clients/{id}` shows:
  - the name and a stat row;
  - one band per entity, listing its engagements (which open the engagement);
  - the team on its active engagements, with their roles;
  - for an unknown or unseen client: "Client not found".
- **AC-4** The command palette lists matching clients and a Clients page.

## 3. Out of scope
Client type, status, office and team fields; contacts (CLI-04); intake (CLI-06); the tax profile; relationships (CLI-03); the client agent dock.
