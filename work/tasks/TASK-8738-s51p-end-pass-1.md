---
id: TASK-8738
title: "S51-PARTIALS-END-1: S51 partials batch 1 end pass: gates, suites, security review and fixes"
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-review
branch: s51p-end-pass-1
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: S51-PARTIALS-END-1
---

## Objective
Run the gates and suites once for the partials batch (#2368–#2376), fix what they find, and review the batch's red and amber work for security.

## Plan (amber)
1. make check-fast and check-fast-frontend; unit suite (-n 4) and the three new replay tests; schema_check for 0985/0986; the batch's DB tests (consultations v2 routes, post-issuance cases, season service, CAS load, consultations log, A-06 consultations).
2. Fixed: consultation detail always authorises (an unchecked route 500s; the consultee holds consultation.read); reopen by the consultee or the QM owner only (allowed_actions on the QM-only action, never a firm-role read); the season build's early return no longer commits a unit with no audit event, a no-op exclusion rolls back, and monitoring notices are audited; fixed-set tests and registries (independence-marked actions, non-creating POSTs, platform schedules, reviewed actions, target kinds with season_manifest_row placed under its client); generated isolation tests and error codes; the CAS commentary's en dash escaped; docs gates (TASK-8734 spec id; TASK-8728's AC list, a miss already on main).
3. Security: walls hold on every new read (consultations log, detail and dashboard count; the posting-batch drawer; season rows and tallies; the release snapshot only adds an item); agents are denied by the matrix and the human-only CHECKs on positions, resolutions and case decisions; exports through safe_xlsx; S3 read failures fail closed.

## Progress log
- `2026-11-19` — Gates green; unit suite 61,224 passed with 8 reds, all fixed and re-run (53,899 on the touched areas); schema_check reversible; the batch's DB tests pass (8 + 4); web 839 vitest tests on the touched areas. Local only: the WeasyPrint classification tests need libgobject (CI has it). Gates and tests run once at the S51 end pass (build first, test last).
