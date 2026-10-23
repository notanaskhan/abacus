---
id: TASK-1013
title: Protected bundle B — retention and legal-hold matrix rows, firm export and incident rows, fresh-MFA list, compliance flags, C16 kinds, glossary and legal-hold status words (Q-02-T30)
spec: SPEC-051
acceptance_criteria: [AC-2]  # SPEC-051 (as TASK-965); the Q-02 epic ACs proved here: AC-17, AC-42
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T30
branch: s6-legal-holds
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The bundle merges first in its train with regenerated matrix and flags, and every new write action is denied to the agent and client principals by generated tests." Repository parts only: no Terraform plan or apply.

## Plan (red zone)
- **Matrix** (`docs/architecture/permission-matrix/`):
  - `evidence.yaml`: `legal_hold.read` (new: `firm_admin`, `security_admin`, `firm_partner`, `quality_partner`); `legal_hold.place` and `.lift` widened with `security_admin` and `firm_partner` (C-10; `level_in(partner)` is the derived `firm_partner`, DEC-132), fresh MFA, agent and system denied. `retention_policy.read` widened to every firm role (the plan's `retention.read`, metadata only); `retention_policy.update` stays the plan's `retention_policy.manage` (DEC-227). `firm_export.request`, `.approve`, `.download`, `.read` (new, no route until Q-02-T43).
  - `platform.yaml`: `incident.manage` (new, `security_admin`; no route until Q-02-T33).
  - Not added: `platform.reference.publish` and `platform.incident.propagate` are staff routes (`STAFF` marker, staff issuer), and `agent_run.read` already exists (SPEC-318) and is widened with Q-02-T41's C6 stub (DEC-227).
- **Human-only register:** `legal_hold.lifted` (decide), `firm_export.declined` (reject), `retention_policy.updated` (decide) join `docs/architecture/human-only-actions.yaml`; migration `0125_human_only_bundle_b` redefines `abacus_human_only_actions()` (down_revision 0115). Rollback: `alembic downgrade 0115` restores 0097's list.
- **Fresh-MFA list:** `docs/architecture/fresh-mfa-actions.yaml` (new, policy file) with a unit test that every listed action exists and carries `mfa_recent: required` (AC-42's first half; Q-02-T37 adds the generated overlay).
- **Flags:** `compliance.legal_holds` and `compliance.firm_export` (`feature-flags/evidence.yaml`), `compliance.incidents` (new `feature-flags/platform.yaml`); created 2026-10-24, expire 2027-04-21 under the DEC-137 override (outside Sep 1 – Oct 20).
- **C16 kinds:** `ai_client_data_changed`, `legal_hold_placed`, `incident_recorded`, `incident_from_accrued`, `firm_export_approval_requested`, `firm_export_ready` registered in `notifications/catalogue.py`. Email text stays database rows (none committed).
- **Words:** glossary rows (agent stage, AI opt-in, AI exclusion, access event, audit checkpoint, retention floor, retention policy, legal hold, hold object, security incident, firm export, run record); status object `legal_hold` (Applying · Active · Releasing · Released).
- **Regenerate:** status vocabulary codegen, `make regenerate`.
- **Tests:** generated matrix and agent-principal suites pick the rows up; `tests/unit/quality/test_fresh_mfa_actions.py`; `tests/integration/test_human_only_guard.py` (drift and refusal per action).

## Progress log
- 2026-10-24: Plan written. Rows, register, migration 0125, flags, kinds, words and contract update landed; regenerated.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-227 | The plan's `retention.read`/`retention_policy.manage` names, staff rows and `agent_run.read` against what S5 shipped | No |

## Human to-dos
- None for this row (no infrastructure change).

## Verification (2026-10-24)
- `uv run pytest tests/unit/quality/test_fresh_mfa_actions.py tests/unit/notifications tests/security/test_permission_matrix_generated.py tests/unit/tools` green; `tests/integration/test_human_only_guard.py` 24 passed; `tests/security/test_agent_principal.py` with notifications 50 passed.
- Pre-existing on `origin/main` (not this change): `tests/unit/identity/test_permission_matrix.py::test_ac20_visible_without_a_firm_allow_filters_on_engagement_membership`, `test_spec020_visible_counts_a_client_role_allowed_by_the_matrix` and two in `test_independence.py` expect the pre-DEC-211 SQL shape (one `client_access_grants.role IN`).
