---
id: TASK-1813
title: Retire clients.v2, engagements.v2 and engagements.acceptance_v2 and the SPEC-025 adapters (P-07-T59, part 1)
spec: SPEC-321
acceptance_criteria: [AC-23, AC-24]  # the v2 index and record answer for every firm
risk_zone: red
status: in-review
epic: P-07
plan_key: P-07-T59
branch: s13r-p07-t59
created: 2026-10-29
updated: 2026-10-29
---

## Objective
"No flag or adapter left behind" (P-07-T59), split by DEC-905: the three rollout flags and SPEC-025's acceptance and independence adapters retire now; dropping `engagement_acceptance` waits for T59b.

## Plan (red)
- **Flags:** remove `clients.v2`, `engagements.v2` and `engagements.acceptance_v2` from `docs/architecture/feature-flags/{organisations,engagements}.yaml`; `make regenerate` (`kernel/_flags.py`, generated tests). Backend gates that answered 404 with a flag off (`organisations/contract.py`, `organisations/conflicts_contract.py`, `engagements/contract.py`, `engagements/acceptance_contract.py`, `engagements/intake_contract.py`, `audit_trail/record_activity_routes.py`) stop reading them; the routes answer for every firm. `contacts.v2` and `engagements.roll_forward_v2` are not T59's and stay.
- **SPA:** routes (`areas.tsx`, `engagements.tsx`, `clients.tsx`) drop their `FeatureGate`s on the three flags; fixture scenarios and journeys stop listing them; the flag-off tests of CLI-01 and ENG-01 go (approval below).
- **Adapters:** remove SPEC-025's `GET …/setup`, `PUT …/acceptance`, `PUT …/letter`, `POST …/independence` and `GET /v1/firm/confirmations` (their only screens went in P-07-T58) with `record_acceptance`, `my_confirmations`, `setup` and their shapes. The matrix actions stay: `acceptance.record`, `independence.confirm`, `letter.record` and `setup.read` still guard v2 and file routes. `answer_independence` and `record_letter` stay (the scenario loader and the v2 recorded letter use them).
- **Not now (T59b):** `engagement_acceptance` stays as G1's and G2's read-only fallback for rows already written (test seeding and local stacks write it directly); its file routes stay with it. T59b moves the shared test seeding to v2 records and drops the table in a reversible migration that refuses while unconverted rows exist (DEC-372: the legacy rows cannot convert faithfully).
- **Security:** a flag-off firm loses nothing it should keep (every v2 route keeps its matrix action, `visible()` and fresh-MFA checks); no route is left without a matrix action; the removed adapters were the only writers of `engagement_acceptance` through the app, so G1 and G2 can no longer be met through SPEC-025's path.
- **Rollback:** revert the PR; flags come back off (registry default false) and the routes return.

## Approval (TEST-001)
Approved by Ayush, 2026-10-29 ("Build P-07-T59"; scope "Split: flags+adapters now"). Removed tests and what supersedes them are listed in the progress log.

## Progress log
- 2026-10-29: built. Flags out of the registry and every reader (backend gates, SPA routes, fixture scenarios, journeys, the Dev seed, the Brightwater Hale acceptance slice). SPEC-025's five routes and `record_acceptance`, `record_letter` (setup's), `my_confirmations`, `setup` and their shapes removed; legacy `Clients.tsx` (list and record, the `clients.v2` fallback) removed with it.
  Tests changed under the approval:
  | Test | Change | Why |
  |---|---|---|
  | contracts `clients` ac4, `engagements_v2` ac13, `intake_import` authorise-first, `acceptance_independence` flags-gate | each replaced 1:1 by a test that the gate still authorises first, reads no flag and the registry lacks it | the flag-off 404 they pinned is gone |
  | contracts `acceptance_independence` refused-whatever-the-flag (6 cases) | 3 cases (agent, system, client), no flag parameter | the flag parameter has no values left |
  | security `test_agent_principal` SPEC-025 PUT acceptance, POST independence (2 of 19, both tests) | removed | the routes are gone; the v2 gates' refusal of an agent is the contract suite's (`acceptance_independence` refused-first) |
  | SPA `legacy/spec303clients.test.tsx` (3) | removed with `legacy/Clients.tsx` | CLI-01 and CLI-02's suites (SPEC-321 AC-20, AC-24) |
  | SPA CLI-01 and ENG-01 route tests | renamed (no flag) | unchanged behaviour |
  | integration `test_acceptance_independence_letter.py` (25) | removed | it drove SPEC-025's retired routes; SPEC-332's suites (P-07-T38 acceptance, P-07-T43 independence, P-07-T15 recorded letter) cover the v2 ground. The acceptance and letter file routes lose their two integration tests here; their authorisation stays pinned by route introspection and fresh-MFA, and they retire with the table in T59b |
  | integration `test_independence_gate.py` | kept, rewired: acceptance seeded as a legacy row, answers through `answer_independence`, the open-request check reads `independence_confirmations` | the gate still reads the legacy row until T59b |
  | security `test_wall_bypass` SPEC-002 AC-5 open independence requests (5) | removed | `GET /v1/firm/confirmations` is gone; `/setup` in the by-id tails becomes ENG-02's `/record` |
  | security `test_tenancy_escape` `/setup`, `/v1/firm/confirmations` | `/record` instead of `/setup`; confirmations dropped | same |
  | `test_acceptance_v2_rules`, P-07-T41 H1 (2) | the old route answers 405; H1's trigger proved by an app-role insert | the route is gone, the trigger stays |
  | P-07-T14 ac13, P-07-T44 flag-off, engagement-hold flag-off, Q-03-T050 catalogue, L1/L2 review completion | each turned into "answers for every firm" (no flag row) | the flags are retired |
  | Q-04-T004 | its example second flag becomes `contacts.v2` | `engagements.v2` is no longer registered |
  Integration and security suites still seed the retired flags as raw `feature_flag_states` rows (harmless: nothing reads them); T59b's seeding rewrite removes them.

## Security review (red, 2026-10-29)
- No route lost an authorisation: every removed `_gate` read only the flag; each route keeps its matrix action (enforced by `AbacusRouter`) and its service's `visible()`; the gates that also authorised keep that and the human-only refusal.
- Surface shrinks: five SPEC-025 routes gone, none added; the matrix actions stay for the v2 and file routes.
- Finding (low, pre-existing, not reachable over HTTP): about twenty gates test `ctx.client` before `ctx.tenant.actor_kind`; an `AgentContext` (no `client`) passed straight to one raises `AttributeError` (500, nothing written) instead of 403. `current_context` only yields `AuthContext`, so only a test that injects an agent context meets it; the order flips in a follow-up, not here.
