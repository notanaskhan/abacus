---
id: TASK-1746
title: N-01-T11 Brightwater Hale intake and Files slice (firm_inbox), footing tests, TS seed export
spec: SPEC-380
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
epic: N-01
plan_key: N-01-T11
branch: s14-n01-t11
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The scenario slice for INB-01, INB-02 and FIL-01 through service APIs: docs@ threads rows 1–17
(23 waiting, 4 unmatched), the Intake team with Grace, footing tests, and the TS seed export.
Acceptance (backlog row): "make seed-demo and fixture mode show identical inbox and Files data
and every footing test passes."

## Plan (amber)
- `brightwater_hale/firm_inbox.py` (slice `firm_inbox`), data `files/firm_inbox_e0.json`, export
  `apps/web/src/fixtures/seed/e0.inbox.json` (`--export`).
- `loader.py`: `organisations.intake_team_created`, `communications.inbound_email_recorded`
  (record_inbound_message + add_attachment), `SLICE_NEEDS`.
- Tests: `tests/unit/synthetic/test_n01t11_firm_inbox_slice.py` (footing, events, export drift),
  `tests/integration/test_n01t11_firm_inbox_load.py` (E0 + slice foots from the rows),
  `apps/web/src/fixtures/seed/inbox-export.test.ts` (INB-01, HOME-01, FIL-01 seeds = export).
- DEC-836. Rollback: revert (opt-in slice).

## Progress log
- `2026-10-29` — Built and run: unit 10, integration 1 (E0 + slice: 17 threads, 18 messages, 23
  waiting, 4 unmatched, 1 ignored, Intake team with Grace), web 7; tests/unit/synthetic 453 green;
  ruff, pyright, lint-imports, banned patterns, secrets scan, eslint, prettier clean.
- Partial by design (DEC-836): W0's three filed files are not loaded until N-01-T15's filing
  exists; FIL-01's Ridgeline documents are held at the data level only until a filing path with
  folder kinds exists. The scenario's matched threads read `staff_selected` (Grace) where INB-01's
  fixture says `contact_email`.

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** G-02-T26.
