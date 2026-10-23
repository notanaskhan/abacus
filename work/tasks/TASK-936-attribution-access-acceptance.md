---
id: TASK-936
title: Independent AC tests for attribution, the policy actor, the human-only guard and access_events (Q-02-T22)
spec: SPEC-304
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T22
branch: q02-t22-attribution-access-acceptance
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The suite fails against seeded violations of each rule and passes on main" (Q-02-T22).

It is written from the plan, not from the code under test (TASK-416, TASK-417, TASK-919):
- Q-02 §3.3 AC-15 to AC-17 and §3.5 AC-23 and AC-25;
- the §5 migration rows for audit attribution, the human-only guard and `access_events`;
- INV-5.

SPEC-304 (the audit log) is the nearest spec on main. The compliance-kernel spec (Q-02-T04) has not been written yet.

## What changed
- `backend/tests/integration/test_q02_attribution_access_acceptance.py`: 26 tests, 71 cases with parameters, against Postgres and the S3 gateway. Seeding goes through the shared `Seeder`.
- Every rule is met with a seeded violation and a control showing the same write is allowed when the rule holds.

### INV-5: what each kind of actor's audit row records
- **Human:** the row names the person.
- **Agent:** the row names the person it acted for and the run.
- **System:** the row names the run's person.
- **Support:** the row names the session.

### AC-15: agent rows name a person
- An agent row without a person is refused, both directly and through the unit of work as the app role.

### AC-16: the dormant policy actor
- A policy row needs a `policy_ref`: NULL and empty are refused.
- A policy context forged in a module commits nothing.

### AC-17: the human-only guard
- Every action in `docs/architecture/human-only-actions.yaml` is refused to both agent and policy actors at the database. The register is the AC's own source.
- Each refused row is otherwise valid, so only the guard can refuse it.
- A person may record every listed action.
- An agent context's unit of work commits none of them.
- A person's decision cannot be rewritten as an agent's.

### AC-23: identifier-only access rows
- A real download over HTTP from encrypted storage leaves exactly one row. It names the tenant, the person, `evidence_content.read`, the version, the client and the engagement.
- The row holds no title, content, SSN, storage key or fingerprint.
- The table has no free-text column.
- Each constrained column refuses free text.
- The writer refuses non-identifiers.

### AC-25: isolation and insert-only
- Tenant B reads none of tenant A's rows and cannot write one for A.
- The app cannot read a partition directly, and cannot UPDATE or DELETE.
- The superuser and the schema owner cannot UPDATE, DELETE or TRUNCATE the parent or any partition (each month and the default), with a row seeded in every one.

## Bugs (strict xfails, see #272)
1. **AC-15: no binding to the transaction's person.** AC-15, with §5's `audit_events_behalf_is_transaction`, binds `on_behalf_of_user_id` to the transaction setting `app.on_behalf_of`, the way migration 0003 binds `app.actor_kind`.
   - Migration 0096 adds no such check, and the unit of work sets no `app.on_behalf_of`.
   - An agent row may therefore name any person, not the one its transaction acts for.
   - Test: `test_q02_t22_an_agent_row_names_the_transactions_person_and_no_other`.
2. **AC-16: no banned-pattern rule.** AC-16 says no code outside `kernel` can build a policy context, and names a banned pattern as the control.
   - No rule flags `TenantContext(..., "policy", ...)` in a module. Only the `ActorKind` Literal (a type hint) and the `policy_ref` CHECK stand in the way.
   - Test: `test_q02_t22_a_banned_pattern_refuses_a_policy_context_in_a_module`.

## Smaller differences from §5 (not tested; noted)
- The agent constraint is named `audit_events_agent_acts_for_a_person`, not `audit_events_agent_needs_person` as AC-15 names it.
- `policy_ref` is `text`, not `uuid`.
- There is no `(tenant_id, on_behalf_of_user_id, seq)` index.

## Progress log
- 2026-10-23: 69 pass and 2 strict xfails. Three runs in a row with `test_access_events`, `test_audit_attribution` and `test_human_only_guard`. Both xfails were checked with `--runxfail`: each fails on its own assertion.
