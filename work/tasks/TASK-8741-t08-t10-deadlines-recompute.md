---
id: TASK-8741
title: "T-08-T10: Filing-deadline recompute, nightly workflow, calendar, detail and export"
spec: SPEC-710
acceptance_criteria: [AC-9, AC-10, AC-11, AC-14, AC-16]
risk_zone: amber
status: in-review
branch: s51q-t08-t10-deadlines-recompute
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-08-T10
---

## Objective
Finish T-08-T10 (TASK-8727): tax states its returns' due dates; practice recomputes filing_deadlines (0962) idempotently on the inputs hash nightly; HOME-03 reads month, week and list views with walls applied and risk computed on read; a deadline's detail names its reference-set versions; exports are one-off xlsx or ics.

## Plan (amber)
1. tax/deadline_facts.py (return_deadlines, exported from tax api).
2. practice/deadlines_service.py: recompute (upsert on the keyed unique, only when inputs_hash moved; extended due date and extension form; owners and signer from the team; an unchanged row rolls back alone), recompute_activity behind practice.filing_deadlines, rows (walls: no row, no day count), detail, export (safe_xlsx; ics with RFC 5545 text escaping of client content).
3. practice/workflows.FilingDeadlineRecomputeWorkflow and the nightly Schedule filing_deadlines_recompute:platform; practice api exports it.
4. filing_deadlines_contract: calendar (month grid three chips + totals), export, detail live; postponement application stays with T-08-T44.
5. Replay history filing-deadlines-v1-recomputed.json; unit and DB tests.

## Progress log
- `2026-11-19` — Built. Only the tax_return source kind is computed (extensions, estimates, notices, closes, reports, 5500s and consents register with their owners); rule_text (C21) is not stored yet (rule_key is null until T-02's rules carry a key); the Sep 15 '12 items' figure needs the deadlines seed; the T-7/T-1 alerts (filing_deadline_alerts) are not sent yet. Gates and tests run once at the S51 end pass (build first, test last).
