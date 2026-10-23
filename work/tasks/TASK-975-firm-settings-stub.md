---
id: TASK-975
title: Firm-settings family contract stub and its consumer tests (G-01-T02, G-01-T03)
spec: SPEC-002
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: G-01
plan_key: G-01-T02; G-01-T03
branch: s6-firm-settings
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The stub merges with E0 examples and the flag, approved on the protected edits", and "the suites run against the stub and fail on any hidden field."

## Plan (red zone)
- **Code:** `identity/settings_contract.py` (settings, people, role templates, annual independence, service lines, offshore, walls v2) and `organisations/settings_contract.py` (offices, teams, the seasonal group): stubs behind `firm_settings.v2`, wired into each module's `ROUTERS`.
- **Policy files:** matrix rows in `identity.yaml` and `organisations.yaml` (new actions only); the flag; status words `membership`, `wall_approval`, `annual_independence`; `docs/architecture/role-templates.yaml` (skeleton).
- **Docs:** `docs/contracts/firm-settings.md`, its README row, DEC-169.
- **Generated:** `make regenerate`, `make generate`, error codes.
- **Tests:** `tests/contracts/firm_settings/test_firm_settings_contract.py` (73); `test_app_gates` lists.
- **Also:** `validate_docs` accepts four-digit TASK numbers (`ID_IN_NAME`), since the three-digit range ran out.
- **Rollback:** revert the commit; no data.

## Progress log
- 2026-10-23: built. The SPEC-002 amendment is recorded in DEC-169 and the contract, until G-01-T09 rewrites SPEC-002's wall clauses. The TypeScript fixture assertions follow with the ADM screens.
