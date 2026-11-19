---
id: TASK-8722
title: "T-06-T27: tax.return_analyst depth modes: asset_evidence, sourcing_position, provision_explainer, time_study_allocation"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: t06-t27-depth-modes
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-06-T27
---

## Objective
tax/analyst_depth_modes.py: the four modes declared once (screen, prompt id, reads, computes, the one write: suggestion.create or proposal.create, never a reserved action), the §7216 gate (both use and ai_disclosure consents before any TRI read, TriConsentRequired → consent_required) and settle (only sentences carrying code's numbers; code's figures, never the model's).

## Plan (red)
1. tax/analyst_depth_modes.py; tests/unit/tax/test_t06t27_depth_modes.py.

## Progress log
- `2026-11-19` — Built; tests pass (5). Not built (prompts come after their eval suites, ADR-079): the four prompts in the registry, the spec v2 update (new compute tools) and the runs through AnalystModeWorkflow; the inline security review of this agent path is at the end pass. Gates and tests run once at the S51 end pass (build first, test last).
