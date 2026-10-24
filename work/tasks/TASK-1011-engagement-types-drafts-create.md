---
id: TASK-1011
title: Engagement-type catalogue, wizard drafts and create — ENG-03 backend, engagement_drafts in migration 0124 (P-07-T16)
spec: SPEC-321
acceptance_criteria: [AC-18, AC-19]
risk_zone: amber
status: done
epic: P-07
plan_key: P-07-T16
branch: s6-clients-engagements
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Hannah creates the Fairhaven EBP audit from a draft in one unit of work and Granite Peak's draft cannot pass step 1 until G1 is met." (P-07-T16; SPEC-321 AC-18, AC-19.)

## Plan (amber zone)
- **Code:** `engagements/type_catalogue.py` *(new)*: the 18-entry code catalogue (family, C1 type, work-item kind, copy, entitlement, group-audit allowance, step fields; no `single_audit`). `engagements/drafts.py` *(new)*: catalogue with availability by the `attest` entitlement; drafts (own scope, `seen_version` autosave, discard); per-step problems and draft gates (G1 from the acceptance decision on the entity's engagement of the draft's type and period); create as one unit of work completing that accepted engagement (period label, methodology pin, work items by cardinality, team through `identity.add_member` so each new member is asked to confirm independence, `engagement.created`), 409 `possible_duplicate` until confirmed, 409 `gate_unmet`, 422 `draft_incomplete`, idempotent per draft and on `Idempotency-Key`. Routes in `contract.py` live behind `engagements.v2`.
- **Migration:** `engagement_drafts` appended to 0124 (branch-only file). Rollback: `alembic downgrade 0123`.
- **Matrix:** `engagement.create` gains the derived `firm_partner` cell (DEC-38 partner path the DEC-132 way). Manager and senior-by-setting cells deferred.
- **Registry:** `engagement_drafts` owned, insert and update columns. Error codes `draft_incomplete`, `entity_outside_client`.
- **Tests:** `tests/integration/test_engagement_drafts.py` (AC-18, AC-19); v2 stub contract test (all but start-acceptance live).
- **Deferred (DEC-225):** start-acceptance (needs P-07-T35's acceptance record; stays 501); a notice response's notice work item (its code and received date are not wizard fields); the 30-day purge job; manager and senior cells on `engagement.create`.

## Progress log
- 2026-10-24: built; 5 integration tests pass. A unit of work must audit, so autosave records `engagement_draft.saved` with the version only (the contract said autosaves are not audited; now they are, identifiers only). Banned pattern L12 caught `Validation` (glossary): renamed `StepCheck`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-225 | Draft G1, completing the accepted engagement, cardinality, start-acceptance deferral | No |
- 2026-10-24: security review fix (DEC-232), failing test first: a draft naming only an entity skipped the client check, and the G1 lookup read the entity's engagements unfiltered. `_check_scope` now always resolves the entity's client, reads the person's walls (`authorise` does not wall a firm-level client resource) and authorises `engagement.create` on it (walled or unknown 404); reads, validation and create re-check it, and the G1 lookup is limited to that client. 6 integration tests pass.
