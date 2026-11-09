---
id: TASK-6532
title: "T-04-T13: TAX-04 Prepare preset in fixture mode on T3"
spec: SPEC-649
acceptance_criteria: [AC-1]  # the row's acceptance (Objective)
screens: [TAX-04]
risk_zone: green
status: in-review
branch: s33-t04-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: T-04-T13
---

## Objective
TAX-04a-e render from scenarios, box 1a 14,820 lights line 3b, approving moves Review 36 to 35
with an ink check, and the mismatch state disables approval with "Resolve 1 mismatch to approve".

## Build
- `apps/web/src/screens/TAX-04/` (`copy.ts` from the handoff spec and the Tax Returns canvas for
  the tree's full names; `index.tsx`; `scenarios.ts`; `TAX-04.test.tsx`) on F-05's
  `EvidenceTriad` in its Prepare preset: `TriadTree` (document variant), `SourceViewer` with the
  region layer and linked-figure tags, Form 1040 leadsheet cards on one `MatchScope` (a box and
  its line share the region's C4 locator, INV-2), `TriadFooter` (Approve Document is a person's
  HumanAction; Unapprove; Issue…).
- States: a unapproved (Review 36, Issues 7), b approved (ink "✓ 1", Review 35, toast,
  Unapprove), c mismatch (3b $14,280 red with flag, approval disabled with its helper), d the
  draft Ridgeline K-1 (box 5 lit with its row; 18A not lit; 2a keeps its flag), e loading pages.
- Motion: box 1a and line 3b light at 700 ms and stay (the poster); at once under reduced
  motion.
- `routes/firm/tax-review.tsx`: the review route opens TAX-04 in fixture builds (production keeps
  the frame until T-04-T05's routes answer).

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). Partial: the MatchStore lights one
  match at a time, so the demo's four-step order (1a 700, 1b 1000, 3b 1950, 3a 2250) is drawn as
  1a with 3b together at 700 ms; 1b with 3a lights on hover or click. Fixture mode only (the
  review tree, regions and approve read T-04-T05's routes, still 501). The page images are F-05's
  form page; the issuer band and boxed blocks of the 1099 composite are the server's render.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3132 | TAX-04 on F-05's triad kit in fixture mode; one lit match at a time | no |
