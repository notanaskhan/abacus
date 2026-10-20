---
id: TASK-301
title: "Planning: materiality decided by the engagement partner, computed from a benchmark; the risk register with RMM and approvals"
spec: SPEC-300
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: red
status: done
branch: task-301-planning
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- Migration 0066:
  - `engagement_materiality` gains its basis and a rationale;
  - new tables `materiality_decisions`, `risks`, `risk_versions` and `risk_approvals`, all insert-only with forced RLS.
- `fieldwork/planning.py`: compute, materiality_history, decide_materiality, rmm, record_risk, approve_risk, risks_for.
- `request_selection` refuses without a decided version (`materiality_undecided`).
- Matrix: `materiality.decide`, `risk.assess`, `risk.approve`.
- schema_check, LIST_EXEMPT, and the pinned route and independence lists.
- Routes:
  - `GET /materiality/versions`, `POST /materiality/decide`;
  - `GET /risks`, `POST /risks`, `POST /risks/{id}/versions`, `POST /risks/{id}/approve`.
- Web: a `Planning` tab (screens/Planning.tsx). Fieldwork's materiality panel becomes read-only and links there.
- Rollback: downgrade 0066 (drops the new tables and columns).

## Definition of done
- [x] `tests/unit/fieldwork/test_planning.py`, `spec300planning.test.tsx`, the gate and independence lists, and the fieldwork screen tests pass; check-fast passes.

## Progress log
- 2026-10-20: built and merged.
