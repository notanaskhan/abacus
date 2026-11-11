---
id: TASK-6816
title: "P-05-T14: AUD-29 Activity in the T2 cockpit: rail row, Timeline, segmented counts, Type and Date chips, search, row Open routing, Download with MFA step-up, Policy empty state"
spec: SPEC-650
acceptance_criteria: [AC-31, AC-32, AC-33, AC-34, AC-35, AC-38]
risk_zone: green
status: in-review
branch: s36-p05-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: P-05-T14
---

## Objective
AUD-29 a–f render from the seed, every row opens its target screen or a registered planned link,
and Download shows only when allowed_actions includes export.create.

## Built
`apps/web/src/screens/AUD-29/` (`copy.ts` with the 23 events verbatim from the handoff and the
server's counts, `Activity.tsx`, `index.tsx`, test): Timeline with the six day separators and
marks (dark check for sign-offs, approvals and decisions; the atom for via-Agent rows), segmented
counts All 23 · Human 12 · via Agent 11 · Policy 0, Type and Date chips, live search (to the host's
query body, never the URL), row Open by kind (WB-09, AUD-06, AUD-07, AUD-03, AUD-08, ENG-02),
Download only with `export.create` (the host steps up MFA), the Policy empty state.
`docs/screens/AUD-29.md` states move to fixture.

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Partials
- The cockpit rail row "Activity" and the live query wiring (`POST …/audit-events/query`) land with
  the A-01 cockpit host; the canvas takes its data and callbacks from that host.
- Type and Date chips render their current value; their menus come with the live wiring.
