---
id: TASK-150
title: "Q-01-T09 · Production adapters P3 and P4: SesTransport in communications/transport.py (configuration set, firm display name, Reply-To, tags carry tenant and message IDs only, scope checker and no-TIN body rule kept) and ClamdScanner in kernel/scanning.py (INSTREAM, 60 MB stream, 30 s timeout, archive-bomb checks first, any error is unscannable)"
spec: SPEC-050
acceptance_criteria: [AC-15, AC-16]
risk_zone: red
status: todo
epic: Q-01
plan_key: Q-01-T09
branch: task-150-ses-clamd-adapters
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
A real clamd testcontainer refuses EICAR and an oversize stream, a timeout yields unscannable, and a blocked message never reaches the SES client.

## Scope
**In**
- `SesTransport` in `communications/transport.py`: configuration set, firm display name, Reply-To, tags carry tenant and message IDs only, scope checker and no-TIN body rule kept
- `ClamdScanner` in `kernel/scanning.py`: INSTREAM, 60 MB stream, 30 s timeout, archive-bomb checks first, any error is unscannable

**Out**
- SES events and suppression (sprint 4)
- The scanner service in Terraform (S1)

## Context to load
- Spec: `docs/specs/SPEC-050-aws-landing-zone-platform.md` (sections: 5 AC-15, AC-16; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/Q-01.md` §0 (lines 10-29), §3 (124-236), §9 (455-524), §10 (525-555), §11 (556-576); read in full: §3 F3 (SES P3, ClamAV P4); §9 row Q-01-T09; §11 R7
- Row: `docs/plan/epics/Q-01.tasks.csv`, plan key Q-01-T09
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- ADRs: ADR-052, ADR-064, ADR-111
- Code: `communications/transport.py`, `communications/scope.py`, `kernel/scanning.py`, `evidence/uploads.py`, the acceptance tests from TASK-153

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is red)

Steps:
1. [ ] Run TASK-153's tests and confirm they fail
2. [ ] Implement `SesTransport` behind the scope and body checks
3. [ ] Implement `ClamdScanner` with the limits
4. [ ] Run the tests unedited until they pass

Files to create or change:
- backend/src/abacus/modules/communications/transport.py
- backend/src/abacus/kernel/scanning.py
- backend/tests/integration/test_ses_transport.py
- backend/tests/integration/test_clamd_scanner.py

Tests to write (mapped to ACs):
- AC-15 → integration: blocked message never calls the SES client; tags carry no address
- AC-16 → integration: clamd testcontainer refuses EICAR and an oversize stream; timeout yields unscannable

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
| clamav/clamav (container), types-boto3 extra sesv2 | per allowlist | scanner test container; typed SES client | Q-01-T05 |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Task file written at kickoff (SU-14). No work started.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Depends on Q-01-T05. Acceptance tests come first.
- ClamAV runs on plaintext in the API before sealing.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Run TASK-153's SES and ClamAV tests and confirm they fail.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
