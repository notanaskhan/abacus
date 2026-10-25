---
id: TASK-1180
title: Brightwater Hale assurance slice through A-01's service APIs - phases as events, EBP profile facts, footing goldens (A-01-T07)
spec: SPEC-330
acceptance_criteria: [AC-16, AC-17]
risk_zone: amber
status: in-progress
epic: A-01
plan_key: A-01-T07
branch: s8a-audits-read
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Loaded E0 foots 27 = 7 + 9 + 6 + 2 + 3 with the Bayside, Meridian and Juniper release and archive records written through services."

## Plan (amber zone)
- **Scenario** (`brightwater_hale/audits.py`): new timeline events per audit, after `engagement_created` and before E0: `engagements.independence_confirmed` (the engagement partner, for audits that move), `assurance.phase_recorded` (one per record-mode step: Fieldwork, In review), `assurance.phase_advanced` (gate phases: Ready to release names G7, Released names G8, at the release date), `assurance.profile_set` (EBP plan kind; Northwind's §103(a)(3)(C)) and `engagements.engagement_archived` (Juniper, Meridian).
- **Loader:** `_engagement_created` stops writing `phase` and creates archived engagements as `delivered`; new handlers call `engagements.api.answer_independence`, `assurance.api.record_phase`, `assurance.api.advance_by_gate` and `assurance.api.update_profile` as the engagement partner; the archive stays a bootstrap write (no record-mode archive service before A-01-T23). `audits.cockpit` joins the scenario's `FLAGS_ON` (the flag's description: "the local seed turns it on for Brightwater Hale"; its registry entry is unchanged).
- **Fixtures:** re-export `make fixtures SNAPSHOT=E0` (the scenario hash changes).
- **Tests:** `tests/integration/test_scenario_assurance.py` (AC-16, AC-17: tiles foot through `GET /v1/audits`' service, every non-Planning phase has its events, no event without a person or a gate).
- **Deferred:** the external release and archive records (Bayside Jul 29, Meridian's CaseWare reference, Juniper's no-report) are A-01-T23's `assurance_external_releases` / `assurance_external_archives`; until then the release is the G8 move and the archive the bootstrap write.
- **Rollback:** revert the commit and re-export the fixtures.

## Progress log
- 2026-10-25: built (partial: the release and archive records wait for A-01-T23). The loader no longer writes `phase`; 75 new timeline events move the 20 audits past Planning through `answer_independence`, `record_phase` and `advance_by_gate` as the engagement partner, and set the 14 EBP profiles through `update_profile`. Releases before the firm's setup keep their own date as business time (Bayside's archive clock reads 13 days at E0). Juniper and Meridian are created Delivered and archived by a bootstrap write after their moves (archived engagements are read-only to the phase service). Scenario version `bh-2026.10.3` with its new hash (the full unit run caught the pinned hash); `make fixtures SNAPSHOT=E0` re-exported (version and hash only). `tests/integration/test_scenario_assurance.py` 7 passed (AC-16 to AC-24 on the E0 load). Not done: an audits read in the fixture export (needs the AUD-01 fixture's designed rows and the live rows reconciled in `exported.test.ts`; A-01-T11).
- 2026-10-25: security review fix: `advance_by_gate` is no longer public, so the gate phases are a seed-only bootstrap write of the derived event (trigger-checked) with its audit row (DEC-310).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-310 | How the scenario reaches each phase through events before A-01-T23 | No |
