---
id: TASK-2227
title: P-04-T43 SHL-16 Checkpoint diff drawer a–f and the restore dialog
spec: SPEC-360
acceptance_criteria: []
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T43
branch: s17-p04-t43
created: 2026-10-30
updated: 2026-10-30
---

## Objective
SHL-16 frames a–f and the restore dialog: `?ov=checkpoints`, filter Agent only / Named only / All,
step timeline, diff rows, reject with a reason, star and rename, import-author variant.

Acceptance (backlog row): "SHL-16a-f match their artboards at Tier C, and Restore always creates a
new checkpoint in the UI."

## Plan
- Flag `review.checkpoints` (review registry, regenerated `_flags.py`).
- `domain/review/checkpoints.ts` (history, detail, writes with `seen_hash`, never optimistic).
- Screen `screens/SHL-16/*`; overlay `checkpoints` (drawer layer) in `routes/firm/sheets*.tsx`;
  fixtures `scenarios/SHL-16.ts` + Checkpoint 3's detail for c; manifest `fixture`; gallery;
  `docs/screens/SHL-16.md`.
- Tests: `SHL-16.test.tsx` a–f, restore, filter.

## Progress log
- 2026-10-30: built in S17 Lane 2 off main; tests and Tier C run in the end review.
