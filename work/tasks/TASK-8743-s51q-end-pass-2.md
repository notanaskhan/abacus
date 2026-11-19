---
id: TASK-8743
title: "S51-PARTIALS-END-2: S51 partials batch 2 end pass: gates, suites, security review and fixes"
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-review
branch: s51q-end-pass-2
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: S51-PARTIALS-END-2
---

## Objective
Run the gates and suites once for batch 2 (#2378–#2381), fix what they find, and review the batch for security.

## Plan (amber)
1. Backend and frontend gates; unit suite (-n 4) with the new replay tests; the batch's DB tests (season execution, deadline recompute, season service, CAS load).
2. Fixed: the glossary's banned name export (export_deadlines); reviewed audit actions for cohorts, row steps, deadlines, two-year explanations and the discarded planner draft; target kinds placed (variance_explanation_version under its engagement, filing_deadline under its client); replay history files renamed to the workflows' slugs; error codes rewritten.
3. Security: the approval grant pins the full row set (a walled approver is refused), execution runs as the system on behalf of the approver and consumes the single-use grant, assignees re-checked; deadline reads remove walled clients before counting; ics escapes client text; exports via safe_xlsx; the planner-draft discard is limited to agent drafts and audited.

## Progress log
- `2026-11-19` — Gates green; unit suite 61,239 passed with 5 reds, all fixed and re-run (760 on the touched areas); the batch's DB tests pass (5). A-09-T42 step 3 stays blocked: AUD-31's group states need the 244-account Harlow & Pike mapping, which the handoff does not give (TASK-8543). Local only: the WeasyPrint classification tests need libgobject. Gates and tests run once at the S51 end pass (build first, test last).
