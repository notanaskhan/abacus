---
id: TASK-2523
title: T-01-T37 Transmission record and acknowledgements
spec: SPEC-501  # T-01 §3.13; docs/contracts/efile-record.md
acceptance_criteria: [AC-7]  # and T-01 §3.13
risk_zone: red
status: done
epic: T-01
plan_key: T-01-T37
branch: s20c-t01-t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Migrations `transmissions` and `efile_acks` (insert-only, human-actor CHECK); member ERO
designation by a firm admin with fresh MFA; `POST transmissions` for the signer holding the ERO
designation only when every required signer has completed, no binding is superseded and the
return is Synced; ack import from the engine report and manual entry with evidence;
`filing.acknowledged` for T-02's status machine; Create issue on rejection; 8879 retention to the
IRS received date plus three years.

Acceptance (backlog row): "Daniel Reyes records the Sep 18 transmission for federal, NY, IL and
CO, Grace Holloway and the agent are refused at every layer, and the four acks move the return
to Accepted."

## Plan (red)
- Migration 0568: `transmissions` (binding, envelope, ERO, method, jurisdictions, date,
  `actor_kind = 'human'` CHECK, `recorded_by = ero_user_id`), `efile_acks` (unique on the ack's
  facts; manual needs evidence, engine file needs its `engine_acks` row),
  `memberships.ero_designated` with a column UPDATE grant, and `abacus_human_only_actions()`
  redefined from the YAML (adds `transmission.recorded`, `efile_ack.recorded` and T-01-T35's
  `delivery_packet.approved`, which had no migration).
- identity: `set_ero` / `ero_designated` (people.py, exported by api.py), audit
  `member.ero_designated`.
- tax/filing.py: `record_transmission` (five layers: INV-4, matrix `function_in(signer)`, live
  person, status machine (`transmission_recorded` now human-only), ERO designation; then the
  binding seen, C7's gate, Synced), `take_up_acks` (from engine_import after the report is
  stored), `record_ack`, `settle` (Accepted or Rejected, `filing.acknowledged`, retention),
  `rejection_issue` (engine_diagnostic issue, Rejected to Fixing).
- tax/engine_sync.py `return_synced`; tax/delivery.py allowed actions; engine_contract routes
  live (+ `POST …/acks/{ack_id}/issue`); registries, schema-check expectations, tenant list.
- Tests: `test_t01t37_transmission_acks.py`.
- Rollback: downgrade 0568 (drops both tables and the column, restores 0566's human-only list);
  routes return to stubs by reverting the contract file.

## Notes
- Nothing moved a return to Awaiting signature (no `envelope_sent` raiser on main): the
  transmission records that move first when the return is still Approved (DEC-1570).
- The T-02-T07 unit row that let the system record a transmission is tightened to refuse it
  (T-01 §3.13: the system is refused at every layer).
- `efile_relocked` and `filing.acknowledged` notification kinds are not registered here.

## Progress log
- `2026-10-31` — Built on `s20c-t01-t37` off main 20f5d5508. T37 tests 6 passed, status machine,
  human-only drift green.
