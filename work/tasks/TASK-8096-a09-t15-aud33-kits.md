---
id: TASK-8096
title: "A-09-T15: ConsolidationWorksheet and EliminationCard kits; AUD-33 a-g in fixture mode"
spec: SPEC-658
acceptance_criteria: [AUD-33 a-g]
risk_zone: green
status: in-review
branch: a09-t15-aud33
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T15
---

## Built
- L2 kits (C-38) in `packages/ui/src/data/`: `ConsolidationWorksheet` (statement grammar, entity
  columns, eliminations with tag chips lighting their cells through the MatchProvider,
  consolidated in 500, pending ink-2; sums nothing) and `EliminationCard` (code, level, amount,
  status; lines, code's computation, citations, provenance; the agent's note through AgentText;
  the person's Approve, disabled while the server says the entry is off). Specimens `c-38-*`.
- `apps/web/src/screens/AUD-33/`: level segmented, the server's tallies (TallyStrip), the
  worksheet, sheet tabs, the docked Eliminations drawer with counts and the server's
  67,840,000 Dr = Cr; states a to g (posted, proposed, off 10,000, Level 2, adjustments empty,
  locked with Reopen, the entity tab). Gallery `AUD-33`; manifest `fixture`. Test: 7 pass.

## Partial
- Per-column section totals ("Total assets" rows) need server rows the C9 v2.1 TB shape lacks;
  the totals are the tally strip's. Proposed in the task's note for A-09-T19's engine.
- New elimination O3 sheet and the Approve 6 confirm list join A-09-T20's service.

## Progress log
- `2026-11-15` — Built.
