---
id: TASK-1185
title: "A-02-T02: the protected bundle - matrix sections (ledger, assurance TB, workpapers ties, connections), the ledger.tb_workpaper flag, TB label and layer status objects, glossary rows"
spec: SPEC-333
acceptance_criteria: [AC-30, AC-31]
risk_zone: red
status: done
epic: A-02
plan_key: A-02-T02
branch: s8a-tb-of-record
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"make generate is clean, import-linter passes and the generated matrix test denies the agent principal every new action." (A-02-T02)

## Plan (red zone)
- **Matrix** (policy files, changed with the code that needs them):
  - `assurance.yaml`: `trial_balance.export` (partner, manager, senior, staff; agent deny; independence). The read, adopt and annotate rows exist (SPEC-309); `tie_out_check.define` exists in `workpapers.yaml` (SPEC-310) and already matches §4.4.
  - `connections.yaml`: `connection.read` (client_admin with `scope_only`; partner, manager, senior; independence), `connection.retry` (client_admin; partner, manager), `connection.reconnect_request` (partner, manager, senior; independence), and the ledger section `ledger.pull` (partner, manager, senior; independence). The ledger module serves no route (it stays dependency-free), so its action sits beside `ledger_import.upload` in the file of the module that serves it. Every new row denies agent and system explicitly.
- **Flag** `ledger.tb_workpaper` in `feature-flags/assurance.yaml` (boolean, default off, `expires: 2027-04-21`, `override: DEC-137`). `connections.portal_v2` and `connections.live_ledger` wait for the code that reads them (T06, T16, T26): DEC-315.
- **Status vocabulary**: `trial_balance_label` (standard, interim, prior, budget, preliminary) and `trial_balance_layer` (unadjusted, aje, rje, final). The connection bridge (`integration` + the retired `connection.*` rows) and the tie tally (`tie_out_tally`) already exist.
- **Glossary**: trial balance of record, TB label, layer, leadsheet (ledger); tie-out check (workpapers); connection consent, reconnect request (connections). No new "Don't use" bans (they would become L12 identifier bans).
- **Deferred to their rows (DEC-315)**: integrations matrix rows, `MODULE_DEPENDENCIES` edges, notification kinds, the connection error codes and the two connection flags (T06, T12, T13, T16, T23); no table is added, so `TABLE_OWNERS` is unchanged.
- **Closed lists**: independence-marked actions in `tests/unit/identity/test_independence.py`.
- **Regenerate**: status vocabulary codegen, then `make regenerate` (matrix, flags, security tests).
- **Rollback**: revert the commit and regenerate.

## Progress log
- 2026-10-25: matrix rows, flag, two registry objects and seven glossary rows added; status codegen and `make regenerate` run (matrix, flags, statuses, security tests, OpenAPI unchanged). Closed lists extended: independence-marked actions (`test_independence.py`), the registry counts in `apps/web/src/status/status.test.ts` (78 objects, 376 rows). New `tests/unit/ledger/test_a02_bundle.py` (12, AC-30, AC-31). Deferred items listed in DEC-315.
- 2026-10-25: verification on the combined branch: `tests/unit tests/contracts tests/security` 28,895 passed, 5 xfailed; the ledger, retrieval, sign-off segregation, review staleness, TB-of-record and `test_schema_check_db` integration files 579 passed; `make check-fast` clean.
- 2026-10-25: main-session security review, five findings fixed in one commit, each with a failing test first. (1) `connection.retry` gains `scope_only` and `independence` (marked list and the generated matrix case updated). (2) `connection.read` must be authorised on an engagement (matrix comment); the new `tests/security/test_c09_tb_authz.py` showed a senior of another engagement was allowed on `Resource.client`, so `authz._roles` now skips the firm-wide roles fallback for `scope_only` reads (only `connection.read` is such a read), and the SPEC-014 firm-level read test expects that refusal. (3) `trial_balance.export` needs `mfa_recent`, is in `fresh-mfa-actions.yaml` and is no wider than `run_trace.export` (staff dropped); DEC-316 amended. (4) and (5): see TASK-1187 and TASK-1186. Found on the way: `test_ac20_visible_without_a_firm_allow_filters_on_engagement_membership` (2 cases) fails when `test_permission_matrix.py` runs alone, already on the base 96fd6939; it passes with the rest of `tests/unit/identity`.
