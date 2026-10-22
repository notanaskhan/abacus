---
id: TASK-422
title: S3 batch - fixes found by the pre-CI local run of the unit, acceptance and contract suites
spec: SPEC-304
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: Q-02
plan_key: S3-CI
branch: s3-ci-fixes
created: 2026-10-22
updated: 2026-10-22
---

## Objective
The S3 batch skipped per-PR CI. Before the one CI run, the full unit, acceptance and contract suites ran locally: 23 failed out of 17,341. This task fixes the ones the batch caused.

## What changed
- **The follow-up tests:**
  - Cause: F-04-T11 put business time on the follow-ups path, and the fake world now stubs `follow_ups.now`. Before that, it reached the tenant clock in the database.
- **The OIDC fake's expiry tests:**
  - Cause: F-04-T16 changed `time.time` to `system_now`, so they patch `system_now` now.
- **`test_system_context`:**
  - Cause: Q-02-T16 added `on_behalf_of_user_id` to the context.
- **`test_permission_matrix`:**
  - The expected roles now include the derived `firm_partner` (DEC-132).
  - The fixture stubs `_partner_level`, because its cases test firm roles alone.
  - A new test covers DEC-132: a partner reads settings, a non-partner doesn't, and nobody gets write.
- **`test_independence`:** the C3 and C5 stubs' client-data actions were added to its expected list.
- **`test_app_gates` (the 201 rule):**
  - The C5 stub's creating routes are in the expected set.
  - Its state changes are listed as not creating.
- **OpenAPI:**
  - A duplicate operation id `proposal` (C3 stub 2 against the roll-forward proposal) was fixed by renaming the stub's handler to `agent_proposal`.
  - The C3 stubs reused the names `ReviewNoteOut`, `DecisionOut`, `ProposalOut`, `SuggestionOut` and `DecideIn`. FastAPI therefore module-prefixed both sides, which renamed schemas existing code imports. The stubs now use `ReviewNoteDetailOut`, `CardDecisionOut`, `AgentProposalOut`, `AgentSuggestionOut` and `CardDecideIn`, and the prefixed names are back to the pre-batch set. The contract doc is updated.
- **`CapabilitiesOut.nav`:** now optional with a default, an additive change, so older clients and fixtures still type-check.
- **`seats_total`:** null for a sandbox firm, matching the SHL-03e fixture. The nav draft type became an alias.
- **`packages/ui` status glyphs:** P-04-T02's new glyph names (`atom`, `atom_olive`, `estimate_badge`) were added to the drawing map.
- **The crop tool:** it reads `<version> sha256:<hex>`, the format F-04-T14 writes, and the parity manifest now accepts screen-route baselines (`page`, from P-01-T02).
- **The idempotency test:** a key literal the secrets scan flagged was renamed.

## Progress log
- 2026-10-22: two failures are left to TASK-461's session, which is changing those files:
  - `RunTraceOut` has fields without classification tags (`test_classification`);
  - the vocabulary has no entry for `TraceRowOut.state` = `info` (`test_f03_status_vocabulary`).
- 2026-10-23: the first CI run (39826821208) failed. Fixes in the second pass:
  - **Agent contexts in tests:** 44 integration failures came from Q-02-T16's check that every agent audit row names its person, because the gateway tests built agent contexts without one. Production builds agent contexts only through `agent_context_for_run`, which always sets the initiator. The tests now pass a person.
  - **Cursor bug (`kernel.listing.keyset`):** a cursor's text key and id are now bound as text and cast in SQL to the column type. The C1 cursor page had failed with "timestamptz < varchar" (F-03-T31).
  - **Expectation updates:**
    - `test_engagements`: `allowed_actions` is on the single read only, not on summaries.
    - `test_identity`: the `/v1/me` v3 keys and `memberships[].firm`.
    - `test_retrieval` and `test_screening`: contexts carry their person.
    - `test_unit_of_work`: the agent case needs a person.
    - `status.test.ts`: P-04-T02 took the registry to 61 objects and 311 rows.
  - **Relay test:** `test_idempotency` relays until nothing is due, since the database is shared.
- 2026-10-23: CI re-run 39854618072 passed 12 of 13 jobs. Integration shard 2 was cancelled at its 20-minute limit with no failures: `tests/durations.json` (Oct 19, `test_identity` at 50 s, now 250 s) had stopped balancing the shards. Fixes:
  - Re-recorded the durations from a full local run (`abacus_tools.ci.shard --record`); the shards now balance at about 4.6 min each locally.
  - Gave the integration job 30 minutes of headroom.
  - `test_entitlements` built its dates with `date.today()` in the host zone, but the check uses the business date (Central). It failed whenever the two differ (UTC+4 at night), so it now uses `kernel.clock.today`.
