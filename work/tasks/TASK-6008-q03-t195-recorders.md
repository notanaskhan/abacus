---
id: TASK-6008
title: "Q-03-T195 every workflow has a replay history: the gap list is empty"
spec: SPEC-000  # row (Q-03-T195)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T195
branch: s29l-q03-t195
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Every registered workflow has a recorded replay history (ADR-090), so the deploy pre-flight names no gap.

## Plan
Five gaps already had histories under shorter names (audit-labels, ses-drain, incident-reminders, intake-purge, withdrawal-purge): the pre-flight gains an ALIASES map and a test that each alias names a registered workflow and a recorded history. Two recorders for the other nine, each running the real workflow against throwaway containers with stub activities: record_simple_jobs (TaxCalendarSweep, ReferenceSetFanOut, notice_analysis ready and failed, knowledge-embedding done and waited) and record_sweeps (ClientImport applied and failed, ClientImportErase, ConnectionHealth, EvidenceIntegrity, PilotMetrics). Twelve histories committed (synthetic ids only), two replay tests. KNOWN_GAPS is empty. Rollback: revert.

## Progress log
- 2026-11-07: built. tests/workflows/test_simple_jobs_replay.py, tests/workflows/test_sweeps_replay.py and tests/unit/tools/test_q03t195_history_preflight.py pass (17). Histories recorded on throwaway containers (Docker).

## Decisions made during this task
DEC-2607
