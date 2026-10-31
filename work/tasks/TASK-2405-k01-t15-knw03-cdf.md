---
id: TASK-2405
title: K-01-T15 KNW-03 c, d and f (draft editing, tailored view, Fix in Knowledge)
spec: SPEC-000  # the backlog row; K-01 §3.4 and the KNW-03 handoff
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: K-01
plan_key: K-01-T15
branch: s19-k01-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
KNW-03 c, d and f: draft editing with lock tooltips, + Step and a Submit for approval banner
action; the tailored view from A-04's program-tailoring contract in fixture mode; the Fix in
Knowledge arrival from run:<id> quoting the C6 run error through AgentText, Retry hidden until P-09.

Acceptance: "KNW-03c, d and f pass Tier C and the state-f banner quotes the 9:58 AM run error
verbatim without rendering markup."

## Plan
Files: `screens/KNW-03/{index.tsx,copy.ts,knw03-cdf.test.tsx}`, `fixtures/{seed/knw03,handlers/knw03,scenarios/KNW-03}.ts`, `routes/firm/knowledge.tsx`, `screens/gallery.tsx`, DEC-1455. No migrations, flags or registry edits.

1. [x] Fixtures c, d, f. 2. [x] Draft editing. 3. [x] Tailoring tags. 4. [x] Run arrival. 5. [x] Tests. 6. [ ] End review.

## Progress log
- `2026-10-30` — Built on `s19-k01-t15` (build-only; tests run at the end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1455 | data-driven draft mode, tailoring as a prop until A-04, run error via AgentText | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review.
