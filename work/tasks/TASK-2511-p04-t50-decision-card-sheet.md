---
id: TASK-2511
title: P-04-T50 SHL-11 Decision card sheet (frames a, b, c, d, f, g, h; ?ov=decision)
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-04
plan_key: P-04-T50
branch: s20-p04-t50
created: 2026-10-30
updated: 2026-10-30
---

## Objective
[AC-1] "SHL-11a and c match their artboards at Tier C, and Hannah Leclerc's frame b offers no
Decide." (backlog row; P-04 §3; the SHL-11 handoff.)

## Plan (amber)
- `apps/web/src/domain/review/decisions.ts`: `useDecisionCard`, `useDecisionWrites` (decide with
  option, factors, rationale, `seen_version`; notify; request analysis) over the generated client.
- `apps/web/src/screens/SHL-11/`: `DecisionSheet` O3 — question card ("?", reserved line with the
  lock, blocking count), context rows, options as a RadioGroup enabled only when the card's
  `allowed_actions` hold `decision.decide`, "Recommended by Accrued Agent" tag on the agent's
  option, qualitative factors, required rationale; Decide (HumanAction) disabled until an option
  and a rationale exist; b's amber "Waiting on … · requested …", Notify and Request more analysis…;
  c's "Decided" line from the option's figures and the rationale as text; d's history rows; f, g;
  h's "Superseded by v3" with the line struck. Copy verbatim in `copy.ts`.
- `?ov=decision:<cardId>` registered (`routes/firm/sheets.tsx`, `sheets-host.tsx`, behind
  `review.grammar_api`).
- Seed: the handoff's full SHL-11 copy for a (Firm range, Prior year, the option details, three
  factors), f (severity question, facts, three options) and g (§754 question, facts, two options,
  note; viewer Daniel Reyes), replacing the stub placeholders; `fixtures/scenarios/SHL-11.ts`.
- Rollback: revert; flag-gated overlay.

## Acceptance
| Check | Test |
|---|---|
| a: content; Decide waits for option and rationale; the body sent | `apps/web/src/screens/SHL-11/SHL-11.test.tsx` |
| b: no Decide for Hannah, radios disabled, Notify | same |
| c, d, f, g, h | same |

## Progress log
- 2026-10-30: built (tests first, run at the end review). DEC-1560. Tier C pixels at the end review.
