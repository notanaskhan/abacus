---
id: TASK-153
title: "Q-01-T12 · Acceptance tests first for the KMS, keyring, SES and ClamAV adapters, written from the P-55 and P-64 text"
spec: SPEC-050
acceptance_criteria: [AC-20, AC-13, AC-14, AC-15, AC-16]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T12
branch: task-153-adapter-acceptance-tests
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
The tests are written before T08 and T09, fail on today's code and pass unedited on T08 and T09, covering wrong tenant, KMS error, key rotation, EICAR, timeout and blocked-body cases.

## Scope
**In**
- Write the acceptance tests from the P-55 and P-64 drafts and SPEC-050 before the adapters exist
- Cases: wrong tenant, KMS error, key rotation, EICAR, timeout, blocked body
- Confirm they fail on today's code

**Out**
- The adapters themselves (TASK-149, TASK-150)
- Editing a test to make it pass

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-20, AC-13, AC-14, AC-15, AC-16; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F3; §9 row Q-01-T12 (rewritten here: tests first, no separate author); §10 Tests and gates
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T12
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-035, ADR-064, ADR-113; drafts P-55 and P-64
- Rewritten row: the ADR-078 separate-author split is void; write the tests first from the spec

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Write `test_kms_key_service.py` (wrong tenant, KMS error, rotation)
2. [ ] Write the SES transport and clamd scanner tests (blocked body, EICAR, timeout, oversize)
3. [ ] Run them and record that they fail on current code
4. [ ] Commit; then implement TASK-149 and TASK-150 until they pass unedited

Files to create or change:
- backend/tests/integration/test_kms_key_service.py (new)
- backend/tests/integration/test_ses_transport.py (new)
- backend/tests/integration/test_clamd_scanner.py (new)

Tests to write (mapped to ACs):
- AC-20 → all tests exist before the adapters and fail on today's code
- AC-13 → wrong-tenant unwrap and KMS error cases
- AC-14 → retired key ID still decodes
- AC-15 → blocked message never reaches the SES client
- AC-16 → EICAR refused, timeout yields unscannable, oversize refused

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
| none | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Task file written at kickoff (SU-14). No work started.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Depends on Q-01-T02 and Q-01-T05; run this task before TASK-149 and TASK-150.
- Test names reference their AC (for example `test_ac13_...`).

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Write the KMS wrong-tenant test from the P-55 text.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
