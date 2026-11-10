---
id: TASK-6902
title: The connect host hands the OAuth answer back to the host the flow began on (A-02-T33, step 2)
spec: SPEC-020  # row A-02-T33, step 2 (the redirect URI); SPEC-333 AC-36/AC-37 start too
acceptance_criteria: [AC-2]
risk_zone: red
status: done
branch: a02-t33-connect-host  # stacked on f09-t09-one-domain (#1585)
created: 2026-11-10
updated: 2026-11-10
---

## Objective
Intuit registers exact redirect URIs, so every firm's flow returns to one host,
`https://connect.<domain>/client/connect/callback` (DEC-3901). Completion needs the person's own
session and a portal session is pinned to its firm's host (ADR-163 §5, ADR-168), so the connect
host must hand the provider's answer back to the host the flow began on. This is the part of
A-02-T33 that blocks registering the production redirect URI.

## Plan (red: written before building)
- **Migration 0790** (head 0763; S34 holds 0770+): `connection_states.origin_host` (insert-only
  for the app, CHECKed host name); global `connection_state_firms` (hash → firm, no app
  privilege) written by the definer trigger `connection_state_firm_note`; the definer
  `connection_state_origin(state_hash, app_host)`, reading the state in its firm's scope only.
  Registered in `schema_check` (`GLOBAL_TABLES`, `DEFINER_FUNCTIONS`, `OWNER_ONLY_FUNCTIONS`) and
  the connections registry (`TABLES`, `INSERT_COLUMNS`).
- **Service:** `connect.start` and `entity.start_entity` take `host` (the routes pass
  `request.headers["host"]`, after `TrustedHosts`); `connect.origin_host` normalises it;
  `connect.handoff_origin(state)` answers the host or `NotFound`, never spends the state.
- **Route:** `POST /v1/connections/handoff` under `PRE_SESSION`; `PRE_SESSION_PATHS` and
  `PUBLIC_ROUTE_EXCEPTIONS` (ROUTE-001); the route inventory and the 200-POST list.
- **Web:** the portal tree gets `/client/connect/callback` (`portal/ConnectCallback.tsx`): ask the
  hand-off, leave for `https://<origin>/client/connect/callback` + the query unchanged, or, on the
  origin, complete with the portal session and return to Connections. The firm bundle's legacy
  page is unchanged (the app host is a staff sign-in's origin).
- **Docs:** DEC-3902, ADR-152 amendment, C20 contract note, cutover runbook step 2, the Intuit
  draft's redirect row.
- **Tests first:** `tests/integration/backfill/test_a02t33_connect_host_handoff.py`,
  `apps/web/src/portal/ConnectCallback.test.tsx`.
- **Rollback:** revert the PR; 0790's downgrade drops the function, trigger, table and column. No
  flag: the hand-off only answers states that name a host, and nothing reaches it until the
  redirect URI is registered.

## Out
- Registering the URI with Intuit, the production stack (Ayush, after deploy).
- Portal sessions and `mfa_recent` (below).

## Progress log
- 2026-11-10: Tests written first; the start test failed (origin null). Built as planned. A first
  definer without the firm note answered nothing: `connection_states` forces row security, so a
  lookup with no tenant sees no row. The global hash-to-firm note (trigger-written; the schema
  gate allows no app privilege on a non-tenant table) fixed it. 13 integration tests and 6 page
  tests pass; ruff, pyright, tsc, eslint clean; client regenerated (`make generate`).
- **Found, not fixed (follow-up):** a portal context carries no `mfa_at`
  (`identity.service.portal_member_context`), so every `mfa_recent` action — `connection.create`
  at start and at completion, `connection.disconnect`, the portal approvals — refuses a portal
  session at the matrix. The portal path's test pins that refusal after authentication (403, not
  401) and moves to 201 when portal sessions carry their second step's time. That is an identity
  decision (DEC-1283 kept portal contexts on `portal_second_step`), so it is not changed here.
- Self security review (reviewer agent): the hand-off core holds (no open redirect, the definer
  reads only the state's own firm and restores `app.tenant_id`, the state is not spent, `Host`
  can't pick a destination). One fix: on the origin host the page sent the code and state through
  the sign-in URL (`?return=`); now it clears the address bar first, holds them in this tab's
  `sessionStorage` across the sign-in, and removes them on first read (test added). Its second
  note is about main's TASK-6543 code (`governance_comms.send_approval` hashes compared to
  themselves), reported, not touched here.
- `tests/unit/identity/test_routing.py`'s pre-session inventory gains the path.
- Stacked on `f09-t09-one-domain` (#1585): the runbook and Intuit rows edited here are the ones
  that PR rewrote, and its DEC-3901/DEC-3903 rows sit beside DEC-3902. Merge #1585 first.
