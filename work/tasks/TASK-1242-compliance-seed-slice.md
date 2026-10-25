---
id: TASK-1242
title: Brightwater Hale compliance seed slice through the scenario loader - FIL-02a policies, FIL-02b holds, INC-2026-005, the flags they sit behind, and the E0 golden check (Q-02-T39)
spec: SPEC-341
acceptance_criteria: [AC-31, AC-34, AC-38]
risk_zone: amber
status: in-review
epic: Q-02
plan_key: Q-02-T39
branch: s8b-docs-compliance
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"make seed-demo loads the slice under the frozen clock and the golden check reads day 4 of 30 and two active holds on Mon Sep 14, 2026." (Q-02-T39)

## Plan (amber zone)
- **Slice:** `abacus_tools/synthetic/scenarios/brightwater_hale/compliance.py`, opt-in `compliance` (needs `people`, for Felix's security-admin template and the partners' level). Events: `platform.flag_set` × 2 (`compliance.legal_holds`, `compliance.incidents`), `evidence.retention_policy_set` × 8 (FIL-02a, Felix), `evidence.legal_hold_placed` × 2 (FIL-02b, Victor Hammond and Neil Ashcroft), `platform.incident_recorded` (INC-2026-005, Felix, Sep 10 2:14 AM CT). `build()`'s default is unchanged, so `SCENARIO_HASH` holds.
- **Loader:** four handlers through the services (`evidence.api.set_policy`, `place_hold` then `legal_hold_apply_batch`/`legal_hold_activate` (the steps `LegalHoldApply` runs), `platform.api.record_incident`, `abacus_tools.flags.set_flag`), each as the named person with a second factor verified now (the matrix's `mfa_recent` reads the system clock). `SLICE_NEEDS` gains `compliance → people`. `make seed-demo SLICE=compliance` passes `--slice`.
- **Module APIs:** `evidence.api` exports `HoldScope`, `HoldView`, `place_hold`, `list_holds`, `legal_hold_apply_batch`, `legal_hold_activate`, `PolicyChange`, `EffectivePolicy`, `set_policy`, `effective_policies`; `platform.api` exports `IncidentFacts`, `IncidentView`, `record_incident`, `clock_day`. No behaviour change.
- **No migration.** No floor, default set or platform row is seeded (DEC-71).
- **Tests:** `tests/unit/scenarios/test_compliance_slice.py` (7); golden `tests/golden/scenario/brightwater_hale/compliance_e0.yaml`; `tests/integration/test_scenario_compliance.py` (4 + 1 strict xfail for the incident reference).
- **Rollback:** revert the commit; nothing is migrated.

## Progress log
- 2026-10-25: built. Unit 99 passed (`tests/unit/scenarios/`); integration `test_scenario_compliance.py` 4 passed, 1 xfailed (strict); `test_scenario_loader.py` and `test_scenario_people.py` 2 passed. `make seed-demo SLICE=compliance` was not run against the shared local database (other agents use it); the integration test runs the same `loader.load` against its own provisioned database.
- **Gaps held (DEC-363):** the incident reference (the register mints INC-2026-001; canon reads INC-2026-005; strict xfail cites this task); the holds' canon dates Aug 12 and Aug 14 predate the firm's Sep 1 setup, so they are placed at setup; the export history waits for `firm_exports` (Q-02-T43); the agent stages wait for a stage service a loader can call for a synthetic firm; `make fixtures` does not export these reads yet (the hand-derived `apps/web/src/fixtures/seed/compliance.ts` stays the fixture source; adding the reads to `fixture_export.py` re-exports every file and needs the equivalence run).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-363 | What the slice seeds, how, and what it leaves | No |

## Questions for the human
- [ ] INC-2026-005: seed four earlier 2026 incidents (canon names only 003 and 004, and two of the four would be invented), or give the incident service an import path that keeps a historical reference (G-02-T18's history)?
- [ ] The holds' Aug 12 and Aug 14 dates: move the firm's setup earlier on the timeline, or keep the setup-instant placement (DEC-213's precedent)?
- [ ] Record-type codes: the slice's eight codes must match counsel's published floor set (Q-02-T31) when it lands, or be renamed then.

## Handoff
- **Current state:** built on this branch, targeted tests green.
- **Exact next step:** answer the questions; then Q-02-T43 for the export history.
