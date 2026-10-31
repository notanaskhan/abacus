---
id: TASK-2700
title: I-01-T17 HOME-02 detail pane per gate class
spec: SPEC-000  # I-01-T17 row and docs/screens/HOME-02.md
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T17
branch: s22-i01-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "States a to d and g render from data, every verb is a HumanAction that opens its
  overlay, and no control appears on an agent-owned element."

## Scope
**In**: `screens/HOME-02/Detail.tsx` (body and pinned footer per class: decision, sign-off,
proposal, final approval, send, generic fallback), the screen's decision draft and the held gate
(b), `?gate=` on a done gate, copy, the C3/C4/C1 fixture frames for HOME-02 (§754 card and its
citations, Ridgeline section ladders and eligibility at L4, Samuel's two agent outputs, the team
roster), `done` rows in the gate handler, gallery artboards selecting their row, tests.
**Out**: evidence pane (I-01-T18); Reassign…, Snooze until… and bulk (I-01-T19, drawn disabled
where allowed); live wire-up (I-01-T21); SIG-01 send host (N-02).

## Plan (amber)
1. Files: `screens/HOME-02/{Detail.tsx,index.tsx,copy.ts,scenarios.ts,HOME-02.detail.test.tsx}`,
   `fixtures/{seed/approvals-detail.ts,handlers/approvals.ts,handlers/human-gates.ts,scenarios/HOME-02.ts}`,
   `screens/gallery.tsx`. No migrations, registry, matrix or flag edits (`home.approvals` exists).
2. Tests first (`HOME-02.detail.test.tsx`): a (card, KV, why through AgentText, options with the
   recommendation as a tag, evidence grouped by source), DV-1 Decide gating and the POST body, b
   decided, not-reserved viewer, c blocked banner + Open proposal → `?ov=approve:`, d Sign off… →
   `?ov=signoff:…:L4_partner`, g Approve adjustments → `?ov=approve:`, final approval →
   SHL-12, unknown subkind → generic; every verb carries `data-human-verb`; no button inside or
   around `data-actor="agent"`.
3. Rollback: revert the PR; the queue (T16) is unchanged in behaviour.

## Progress log
- `2026-10-31` — built; tsc and eslint clean on the touched files. Tests run at the S22 end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1750 (classes, verbs, draft, held gate) | handoff draws Decide in the detail; other verbs are their owners' sheets | No |
