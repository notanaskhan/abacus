---
id: TASK-7310
title: "T-04-T34: TAX-08 Assistant states a, a2, b, c, d, e and f in fixture mode as an O2 420 drawer over TAX-05 without scrim"
spec: SPEC-649
acceptance_criteria: [AC-6]  # the spec's section ids (validate_docs reads AC-<n>)
risk_zone: green
status: in-review
branch: s37-t04-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T34
---

## Objective
Seven TAX-08 artboards render, approving shows the 9:31 AM checkpoint line with Undo for 10 s and
Issues 4 to 3, and no control on an agent-owned element reads approve, send or sign.

## Plan
- `apps/web/src/screens/TAX-08/` (`copy.ts` verbatim from the handoff spec, `Assistant.tsx`,
  `index.tsx`, `TAX-08.test.tsx`): the O2 drawer (420, no scrim), context strip, the person's
  bubble, the agent block through `AgentText`, the K-1 card (hover lights the viewer's box;
  purple only on the lit row through the match tokens), treatment chips, the E7 `ApprovalCard`
  (Approve adjustments is a `HumanAction`; Edit… makes the after values editable; Reject… asks a
  reason), the applied line with Undo for 10 s (DEC-24), the rejected line, the follow-up table,
  idle prompt cards, thinking narration, loading and not-allowed.
- `docs/screens/TAX-08.md`: states now `fixture`.
- g and h stay hidden (W-03's saved prompts).
- No API change.

## Partial
- Live: the thread runs on P-10-T43's sessions core once T-04-T37 adds `tax.assistant`; the
  host wiring (the SHL-13 dock renderer's RunStore over the session stream, Issues 4 → 3 from the
  server's count, SHL-08 source opening) lands with that row and T-04-T29's swap.

## Progress log
- `2026-11-12` — Built (S37). Prettier clean; vitest written, run at the end pass.
