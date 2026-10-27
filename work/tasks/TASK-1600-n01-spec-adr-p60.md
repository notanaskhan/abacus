---
id: TASK-1600
title: SPEC-380 firm intake and Files, ADR P-60 part 1 (N-01-T01)
spec: SPEC-380
acceptance_criteria: [AC-1, AC-2, AC-8, AC-12, AC-20]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T01
branch: s13-ready
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Write the N-01 spec and ADR P-60 part 1 so the contract stub, migration and intake work can start.

## Plan
- `docs/specs/SPEC-380-firm-intake-and-files.md`: actors, ACs from N-01 §3, human-only actions, audit events, task plans T02–T30.
- `docs/adr/ADR-210-firm-intake-channel-agnostic.md` (P-60 part 1), accepted under AMENDMENT-solo; `docs/adr/backlog.md` row.
- Decisions DEC-700 (split), DEC-701 (intake scope, OQ-2), DEC-702 (threading, unmatched staff intake; OQ-7, OQ-8).
- Rollback: revert; docs only.

## Progress log
- 2026-10-27: written in the S13 sequential build (S13 block: migrations 0270–0299, TASK-1600–1699, DEC-700–749, ED-200–219, SPEC-380–399, ADR-210–219, RB-60–69). Docs only; validate_docs runs in the end-of-batch pass.
