---
id: TASK-911
title: Independent AC tests for entitlements, /v1/me capabilities, the list envelope and work-item subtype cardinality (F-03-T34)
spec: SPEC-047
acceptance_criteria: [AC-11, AC-14]
risk_zone: amber
status: done
epic: F-03
plan_key: F-03-T34
branch: f03-t34-ac-tests
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Tests written in AY's session cover every field of the Me contract and every cardinality rule,
and pass on main." (ADR-078 independent tests for F-03-T22, T28, T29, T30.) Written from F-03
stories 1.1, 6.1, 6.2, 7.1 and 8.1, §4.3 and §4.6, SPEC-047 AC-11 and AC-14, the C1 contract
(`docs/contracts/work-items.md`), ADR-145, ADR-147, ADR-148 and DEC-129, not from the code.

## Plan
Tests only; no product code, migration or registry change.
- `backend/tests/integration/test_f03_independent_acceptance.py`, against Postgres
  (`migrated_db`): seeding as the superuser through `Seeder`, every behaviour as the app role
  (services through `tenant_session`, HTTP through `create_app()` with the fake identity provider).
  - Cardinality (AC-11, Story 1.1): Copperleaf's 12 closes and the 13th period (409
    `work_item_exists`, facts `{"kind": "close"}`, nothing written); a period is unique per
    engagement, not per firm; a second assurance item (409); one assurance item for each of the
    ten attest types and none for the four non-attest types, one primary entity for all;
    Thornbury's four returns across the decedent and the estate; notices and advisory projects
    take more than one; an unregistered kind (409 `unknown_work_item_kind`); partner and manager
    allowed, senior and an agent principal denied; another firm's engagement 404.
  - Entitlements (Story 7.1): a route guarded by `require_entitlement("attest")` answers 403
    `entitlement_required` naming the module, 200 with an in-date row, 403 when switched off, not
    yet valid or lapsed, 403 when only another firm holds it; no `ff.*` or module-named flag in
    the registry and the registry parser refuses them.
  - Me contract (AC-14, Story 6.2): every field on `/v1/me/capabilities` (capabilities, roles,
    flags, entitlements, office, tz, MFA window, server time, portal); Grace Holloway's binder
    and invitation actions with no evidence or comment action; no authorisation check recorded;
    the portal shell and scopes for owner, K-1, third-party and union grants (DEC-129);
    `allowed_actions` on the engagement projection, none for writing on an archived engagement.
  - List envelope (Story 8.1, §4.6): the envelope fields, newest first, counts that ignore the
    status filter, opaque cursors that page without overlap, cursors bound to firm and filters
    (422 `cursor_invalid`, no facts), default 50 and maximum 200, walled engagements left out of
    items and counts, identifier-only error facts.
- Rollback: delete the file.

## Strict xfails: bugs the tests expose (not fixed here)
1. **`/v1/me` lacks the Me contract fields.** It returns no `capabilities`, `roles`, `flags`,
   `entitlements`, `office_id`, `tz` or `mfa_recent_until`; only `/v1/me/capabilities` does.
   Story 6.2, §4.3 ("Extended Me") and SPEC-047 AC-14 require both.
   (`test_ac14_me_carries_the_same_fields_as_capabilities`)
2. **No `read_only_reason` on record projections.** `GET /v1/engagements/{id}` for an archived
   engagement has `allowed_actions` but no `read_only_reason` (`archived`, `walled`, `gate_g2`,
   `role`, `mfa_required`, `flag_off`, `entitlement`). Story 6.2, SPEC-047 AC-14.
   (`test_ac14_an_archived_engagement_says_why_it_is_read_only`)
3. **Walled engagement capabilities answer 200, not 404 (INV-3).**
   `GET /v1/me/capabilities?engagement_id=` resolves the engagement without the wall check, so a
   walled person learns it exists. Story 6.1 and the `capabilities()` docstring require 404.
   (`test_story_6_1_a_walled_engagements_capabilities_are_404`)

## Progress log
- 2026-10-23: 50 cases written and run against Postgres: 47 pass, 3 strict xfail (above).
  ruff, pyright, banned_patterns, validate_docs and check-generated green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The cardinality 409 code is asserted as `work_item_exists` | F-03 §4.6 lists `cardinality_exceeded`, but the frozen C1 contract (`docs/contracts/work-items.md` §6) names `work_item_exists`; the contract binds consumers | no |
| The list filter is `status` | Story 8.1 says `tile`; C1's live list (F-03-T31) exposes the tile as `status`; the counts-ignore-the-filter rule is tested on it | no |
| Not tested: the `total_capped` threshold (10,000 rows) and the flag-expiry and owner rule "after the Dec 14-18 bundle" | Too large for an integration test; the bundle has not happened (2026-10-23) | no |

## Gotchas and discoveries
- An `AuthContext` whose tenant context says `actor_kind="agent"` is still a person to
  `authorise`; an agent principal is an `AgentContext`. The agent-deny case builds one.
