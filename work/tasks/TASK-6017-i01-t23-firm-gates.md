---
id: TASK-6017
title: "I-01-T23 firm-level gates: methodology version and wall approvals on HOME-02"
spec: SPEC-000  # row (I-01-T23)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: I-01
plan_key: I-01-T23
branch: s29m-i01-t23-firm-gates
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-08
updated: 2026-11-08
---

## Objective
I-01-T23's methodology version and wall approvals were left out: both belong to no engagement, and C13's projection, its event handler and its read filter were all keyed by engagement.

## Plan
C13 firm scope (review/gates.py): GateSource.scope ('engagement' default, 'firm') and decides; firm rows carry no engagement; an event naming no engagement reconciles firm sources; the read filter admits a firm row only when assigned to the caller or their firm role allows decides, and never when it names a client they are walled from. authz: firm_role_allows and not_walled_client (identity.api). Sources (review/firm_gates.py): methodology_version_approval (decides methodology.approve; KNW-02) and wall_approval (assigned_only to the named partner; ADM-03 drawer). methodology: MethodologyVersionApproved emitted on approve; MethodologyReviewRequested also on both import paths (K-01 AC3.7); gate_reads.py. identity: walls_awaiting_approval. C13_EVENTS + pinned list. BOUND-002: review -> methodology edge. Web: subkind words, HOME-02 hosts for KNW-02 and ADM-03. No migration (human_gates.engagement_id was already nullable). Rollback: revert.

## Progress log
- 2026-11-08: built. Integration test_i01t23_firm_gates (3) with the existing gate suites p04t16, p04t17, i01t04: 45 passed. Unit test_i01t23_firm_scope, home subkinds, C13 contract: 28 passed. Web HOME-01, HOME-02, home, routes: 146 passed. pyright src, ruff, lint-imports, banned patterns, tsc, eslint clean.

## Decisions made during this task
DEC-2613
