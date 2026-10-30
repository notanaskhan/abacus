---
id: TASK-2143
title: F-06-T13 Signing and tax-index parity lock, specimen walks, N-02 and T-02 hand-off
spec: SPEC-000  # F-06-T13 row; F-06 §5.4 is the spec
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T13
branch: s16-f06-t13
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Lock T16, TPL-16 and TPL-01 at Tier B (the Decision Day parity-tier reading, F-06 §5.4).

## Plan
- `docs/design/parity-manifest.json`: twelve locked Tier B entries — T16 b, c (gallery
  `t16-signing-ceremony`), TPL-16 b, d, e, f, g and TPL-01 a–e (registered screens) — each pinned
  to its handoff PNG's SHA-256 (`crop_handoff --pin`). TPL-16 a, c and T16 a stay Tier C
  screenshots (DF-11, DF-12).
- Screen contracts T16, TPL-16, TPL-01: the parity rows read "B locked" and a hand-off section
  names the consumer (N-02 POR-06, T-02 TAX-01).
- The specimen walks are `e2e/visual/parity.spec.ts` over these entries.

## Progress log
- 2026-10-30: manifest entries added and pinned; the parity run (needs `pnpm visual:baselines` from
  the handoff and the gallery build) is at the end review — selectors are confirmed there.
