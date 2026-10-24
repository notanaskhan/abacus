---
id: TASK-1163
title: Draft P-47 as ADR-169 (proposed) — canonical run states with the legacy map, durable run records under engagement retention (C-12), the C6 v1 stub shape (Q-02-T34)
spec: SPEC-051
acceptance_criteria: [AC-2]  # the Q-02 row: P-47 lists every run-record field and its retention; acceptance is not this task's
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T34
branch: s7-small-items-incidents
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"P-47 is Accepted by Fri Feb 19 and lists every run-record field and its retention." This task drafts it; acceptance is recorded in the ADR when it happens (not by this task).

## Plan (red zone, a document)
- Number: the next free on `origin/main` (ADR-168 was the last), so ADR-169; the plan's "ADR-147" alias is void (ADR-147 is the role catalogue).
- `docs/adr/ADR-169-canonical-run-states-durable-run-records-c6-v1.md`, status `proposed`; index row in `docs/adr/README.md`; `docs/adr/backlog.md` P-47 row → ADR-169, proposed.
- Content: the 11 stored and 3 derived states and the transitions (chapter 05 §5.3.6); the legacy map and an additive migration with a generated `status` (ADR-090 patches); which runs get a record, when, how it joins the hash chain; every record field with its classification and retention; the C6 v1 shape additive to v0.
- No code, no migration. Rollback: delete the draft.

## Progress log
- 2026-10-24: drafted as ADR-169, proposed. Additions to Q-02 §4.2's field list, for the deciders: `stage` (shadow or live; shadow runs keep records as promotion evidence) and the terminal state inside `outcome`. Open for acceptance: the firm-level runs' anchor (P-14's record-class registry) and whether `cancelled` maps to `failed` in the compatibility `status`.
