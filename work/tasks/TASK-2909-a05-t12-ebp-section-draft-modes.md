---
id: TASK-2909
title: A-05-T12 EBP modes on workpapers.section_drafter
spec: SPEC-640
acceptance_criteria: [AC-10]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T12
branch: s24-a05-t12 (stacked on s24-a05-t09)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-05's six EBP modes as version 2 of A-04's one section-drafter spec, with per-mode paper plans; no second spec, workflow or flag.

## Acceptance (backlog)

A run in an EBP mode writes only suggestions and proposed issues, every proposed value carries a verified citation, a run Marcus Delaney starts is attributed 'Marcus Delaney via Agent', and agents/specs holds one workpapers.section_drafter spec with one evaluation_suite.

## Plan

- Spec v2: modes `ebp_provisions`, `ebp_attribute`, `ebp_reconcile`, `ebp_trust`, `ebp_form5500`, `related_parties` (base prompt until each mode's own lands; $0.25 per section, A-05 §6's baseline); task scope adds `ebp.read`; `client_data: none` keeps every mode synthetic-only (ADR-115). `_specs.py` regenerated.
- `agents/section_sources.register_mode_plan` / `mode_kinds`; `section_draft.start` refuses a mode on a paper kind outside its plan (409 `mode_not_for_paper`).
- `assurance/ebp_designed.MODE_PLANS` registered from `assurance.api` (A-05 §6's table; `related_parties` drafts AUD-27's records, so nothing until A-05-T48).
- The run's write path is A-04-T11's workflow, unchanged: suggestions only through `create_suggestion`, C4-verified citations, `on_behalf_of_user_id` attribution.
- Deferred (DEC-1956): the Form5500TieOut child workflow (A-05-T36 with EBP-07's service); per-mode compute hooks beyond the paper plan land with each mode's prompt.
- Test: `tests/unit/agents/test_a05t12_ebp_modes.py`.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-05-T09. Tests written, not run.
