---
id: RB-83
title: "Today brief rollout, budgets and incidents (I-02): today_brief.enabled per firm, the staging walk, p95 budgets, a stuck build, a §7216 refusal"
owner: builder
owning_epic: I-02
alarms: [today-get-p95, today-drill-p95, today-first-open-build-p95]
last_rehearsed: never
rehearse_by: 2028-06-20
---
# RB-83 · Today brief (I-02)

| Field | Value |
|---|---|
| Owner | ayushkbhatia (`today_brief.enabled`'s registry owner) |
| Flag | `today_brief.enabled` (boolean, default off). On only for synthetic tenants (Brightwater Hale, the synthetic canary) until retirement (DEC-1391: no live pilot firm) |
| Budgets (p95) | `GET /v1/me/today` 300 ms · `GET /v1/me/today/work-items/{id}` (drill-in) 300 ms · first-open build (claim → ready) 20 s |
| Depends on | `workbench.enabled` for the composer; `agent_runtime.v2`; `briefing.today` at stage `synthetic` |

## 1. Turn it on for a synthetic tenant
1. Confirm the tenant is synthetic (`is_synthetic_firm`) and `workbench.enabled` is on.
2. Set `today_brief.enabled` for the tenant through the flag admin (never a seed or migration).
3. Walk J13 step 1 and J23 step 1 at E0 on staging (`make e2e` with the staging project, or by hand
   as Daniel Reyes and Margaret Okonkwo): counts equal HOME-01's, the brief's rows link to their
   sources, the 9:26 question answers with citations, "Approve the four sign-offs" is refused
   toward sign-off.
4. Record the walk in the task log (date, tenant, p95 read from the dashboards).

## 2. Budgets
- Read `today-get-p95`, `today-drill-p95` and `today-first-open-build-p95` after the walk. A
  breach: check the briefing dispatch's three-at-once cap and the C13 gate read first; a build
  over 20 s shows "Building your brief…" with its counts, never a blank panel.

## 3. A stuck build
- A `building` row older than 10 minutes: the dispatch's staleness re-claims it on the next open
  (I-02-T13). To force: `POST /v1/me/today/builds {mode: force}` as the viewer (three a day; 429
  `rebuild_limit` after).

## 4. A §7216 refusal
- An engagement whose taxpayer lacks consent shows its card "Agents are off for this taxpayer";
  the model is never called: dispatch's `capability_ready` refuses first, and (I-02-T22,
  DEC-4945) the call itself names the engagement's TRI subjects so the gateway refuses it too.

## 5. Roll back
- Turn `today_brief.enabled` off for the tenant: HOME-01 draws alone, the panel, link and bell
  entry go; briefings and snapshots stay (insert-only, 90 days).

## 6. Retire
- After the builder's go on the Thu Jun 22, 2028 train: retire the flag into the entitlement, or
  renew once to Aug 31, 2028 (ADR-089).
