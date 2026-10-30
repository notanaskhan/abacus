---
id: TASK-2122
title: K-01-T12 KNW-03 read API, the methodology_step citable and the export
spec: SPEC-008
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T12
branch: s16-k01-t12
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Make K-01's program and step reads live, register the `methodology_step` C4 citable and export a
version byte-identically (K-01 §3.4).

Acceptance (backlog row): "A methodology_step citation to BH-EBP-110 step 4 at v3 verifies, the
same key at v2 resolves to its v2 step, and two exports of v3 are byte-identical."

## Progress log
- 2026-10-29: built (S16 block; tests run at the batch's end review). DEC-1169.
