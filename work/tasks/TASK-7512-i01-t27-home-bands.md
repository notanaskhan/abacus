---
id: TASK-7512
title: I-01-T27 wire the R2 To-dos and Mentions bands into the live HOME-01
plan_key: I-01-T27
spec: SPEC-650  # AC-7 (HOME-01h), AC-29 (HOME-01i)
acceptance_criteria: [AC-7, AC-29]  # h and i bands on HOME-01, header unchanged at 11 for Daniel, flag off restores the pre-R2 composition
risk_zone: green
status: in-review
branch: i01-t27-home-bands
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Mount I-01-T24's `HomeBands` in the live HOME-01 composition after "Approvals & sends", behind
P-05's `collaboration.v2`, with a written flip and rollback.

## Plan
- `apps/web/src/screens/HOME-01/index.tsx`: with `collaboration.v2` on, `listTodos` (`assignee=me`,
  `status=open`; the same query as My to-dos) and the mentions feed (`tab=mentions`, today) feed
  `HomeBands` in the Queue after Waiting on you; off, neither query runs and nothing renders. A
  mention opens its engagement thread (`feedHref`); a to-do row stays inert until SHL-17 has an
  overlay route (P-05; it is `planned` in the manifest).
- `fixtures/scenarios/HOME-01.ts`: `bands-a2`, `bands-h`, `bands-i` with the flag on and the
  band frames' seeded rows.
- Tests in `HOME-01.test.tsx`; the flip and rollback in `docs/runbooks/RB-70-home-counts.md`.

## Partial
- The staging check and the per-firm flips (Tue 19:00 CT from May 2, 2028, Q-04's calendar) need
  staging and a live firm (DEC-1391).
- SHL-17 has no overlay route yet, so a to-do row does not open it.

## Progress log
- `2026-11-12` — Wired (DEC-4512). Tests run at the S39 end pass.
- `2026-11-12` — End pass (lint, plan 04 §1.7): `HomeBands` (and its copy, now `bandsCopy.ts`, and test) moved from `components/screens/HOME-01` into `screens/HOME-01`; `feedHref` reaches the screen through the firm shell part `shell/firm/notification-links.ts`. C-contract `home-and-gates.md` updated.
