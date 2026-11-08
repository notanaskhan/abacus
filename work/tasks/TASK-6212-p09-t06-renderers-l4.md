---
id: TASK-6212
title: P-09-T06 AgentBlocks renderers, specimens and L4
spec: SPEC-648
acceptance_criteria: [AC-9]
risk_zone: amber
status: in-review
epic: P-09
plan_key: P-09-T06
branch: s31-p09-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Finish TASK-5004's renderer half. Checked on main: `packages/ui/src/agent/blocks.tsx` renders React
nodes only, `sanitiseAgentText` on every string, facts through `format.ts`, cites as C4's
`CiteMarker`, an unknown part as a neutral row; the `p-09-agent-blocks` specimen shows all nine
parts on the seed's Northwind figures. The open clause was "ESLint L4 extended to the new fields".

## Plan (amber)
- `apps/web/eslint.config.js` L4: `args_summary` (C6 v1.1's tool-call arguments, model-written)
  joins `model_text`; a value cast as `AgentBlocksPayload` may go only to `<AgentBlocks />`.
- Probed on a throwaway file (all three cases flagged); the repo lints clean with the rule.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2812 | L4 by field name and by the payload's type cast | no |
