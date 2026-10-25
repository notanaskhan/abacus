---
id: TASK-5000
title: "C6 v1: the run read, records read and writes; the trace counts suggestions and proposals; numbering and owner record"
spec: SPEC-318
acceptance_criteria: [AC-7]
risk_zone: amber
status: done
branch: task-5000-c6-v1
worktree: agentwt
created: 2026-10-25
updated: 2026-10-25
---

## Plan keys
Q-02-T45, P-09-T07, P-09-T08, P-09-T10 (partial).

## Plan
- **Decision log:** DEC-336 records the TASK-5000+ block, notanaskhan as owner of P-09 and P-10 (the Q-02-T45 condition), and the trace part of DEC-87.
- **Agents:**
  - `runs.py`: `run_view` (with `run_record_sha256` and `allowed_actions`), `records_read_for`, `writes_for` and `written_counts`;
  - the trace timeline shows decisions on suggestions and proposals;
  - `RUNTIME_LABEL` becomes "Accrued Agent runtime".
- **Repository:** `run_writes` reads the 0095 tables with their newest decisions (LIST_EXEMPT).
- **Routes:** `GET /v1/agent-runs/{id}`, `/trace/records-read` and `/trace/writes`, all on `agent_run.read`.
- **Web:** the trace drawer gets a Segmented control (Timeline, Records read, Writes & approvals), plus a `RunWrites` list.
- **Rollback:** revert the PR. There are no migrations.

## Progress log
- The dev database needed `bootstrap.sql` re-applied (pg_trgm, btree_gin) for the cofounder's migrations, then moved 0100 → 0157.
- Dev smoke test, as the partner, on a screener run:
  - the run view gives a stable SHA and allowed actions `[agent_run.read, run_trace.export]`;
  - records read: evidence_version 1 and task_scope 2;
  - writes: one pending screening;
  - the trace's runtime reads "Accrued Agent runtime".
- The dev data has no suggestion or proposal rows yet, so a unit test covers the counting. The `run_writes` SQL ran against the 0157 schema.

## Definition of done
- [x] test_runs (13), classification, status vocabulary, api, route introspection and matrix tests pass.
- [x] spec318runs passes (6 tests).
- [x] check-fast passes.
