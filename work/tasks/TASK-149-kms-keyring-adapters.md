---
id: TASK-149
title: "Q-01-T08 · Production adapters P1 and P2: KmsKeyService in kernel/crypto (KMS Encrypt and Decrypt of each per-object data key with encryption context abacus:tenant and abacus:purpose, deterministic tenant alias as key_id, fail closed on any KMS error) and the Temporal payload keyring from Secrets Manager (several key IDs, one current); settings validators require both outside local and test"
spec: SPEC-050
acceptance_criteria: [AC-13, AC-14, AC-17]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T08
branch: task-149-kms-keyring-adapters
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan below into this file first, then build.
> - If scope must change, add it to *Questions for the human* and carry on with the plan's proposed option.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.
> - Region is us-east-2 (DEC-03). Terraform apply is run by the builder by hand, never from a session; a session runs `fmt`, `validate`, `tflint`, `trivy config` and read-only `plan` only.
> - Never write an amount; refer to "the DEC-03 envelope".

## Objective
Outside local and test the process refuses to start without KMS and keyring settings, a wrong-tenant unwrap fails, and a payload sealed under a retired key ID still decodes.

## Scope
**In**
- `KmsKeyService` in `kernel/crypto`: KMS Encrypt and Decrypt of each per-object data key with encryption context `abacus:tenant` and `abacus:purpose`, deterministic tenant alias as `key_id`, fail closed on any KMS error
- Temporal payload keyring from Secrets Manager: several key IDs, one current
- Settings validators that require both outside local and test (and refuse an `anthropic_api_key` and a `fake` route in production)

**Out**
- Tenant key creation (`TenantKeyWorkflow`, sprint 2)
- SES and ClamAV adapters (T09)
- Any fallback to `LocalKeyService`

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-13, AC-14, AC-17; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F3 (KMS P1, payload keyring P2, settings); §9 row Q-01-T08; §11 R8
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T08
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-035, ADR-113, ADR-114
- Code: `kernel/crypto`, `kernel/config.py`, the acceptance tests from TASK-153
- Reference pattern to copy: `LocalKeyService`

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Run TASK-153's tests and confirm they fail
2. [ ] Implement `KmsKeyService.wrap/unwrap` with encryption context
3. [ ] Implement the keyring loader and rotation behaviour
4. [ ] Add the settings validators
5. [ ] Run the tests unedited until they pass

Files to create or change:
- backend/src/abacus/kernel/crypto/ (KmsKeyService, keyring)
- backend/src/abacus/kernel/config.py
- backend/tests/integration/test_kms_key_service.py

Tests to write (mapped to ACs):
- AC-13 → integration: wrong-tenant unwrap raises DecryptionError; any KMS error fails sealing and opening
- AC-14 → integration: a payload sealed under a retired-but-present key ID decodes
- AC-17 → unit: staging/production settings refuse to start without KMS and keyring settings

## Definition of done
- [ ] All listed ACs have passing tests (or recorded manual evidence for apply-dependent checks) that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies beyond the allowlist rows listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] `terraform apply` was run by the builder by hand where the task needs it, never from a session; plan output is in the progress log
- [ ] Module README and relevant docs updated
- [ ] Decisions below recorded; ADR raised where needed

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Decision |
|---|---|---|---|
| types-boto3 extras kms, secretsmanager | per allowlist | typed KMS and Secrets Manager clients | Q-01-T05 |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Task file written at kickoff (SU-14). No work started.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Depends on Q-01-T05. Write the acceptance tests first (TASK-153); never edit them to pass.
- Fail closed: no fallback to `LocalKeyService`.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Read TASK-153's tests and confirm they fail on current code.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
