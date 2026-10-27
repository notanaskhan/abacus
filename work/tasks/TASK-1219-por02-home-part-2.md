---
id: TASK-1219
title: POR-02 frontend part 2 — d, e (scope switcher and role chips), g and h fixture-only, M at 390 (P-08-T23)
spec: SPEC-320
acceptance_criteria: [AC-15, AC-16]
risk_zone: green
status: done
epic: P-08
plan_key: P-08-T23
branch: s8b-portal-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Scenario tests for d, e, g, h and M pass, and Meera Shah's home lists nothing of the Ridgeline return."

## What was built
- `screens/POR-02/index.tsx`: the to-do kind registry gains glyphs and the R2 kinds (reconnect, review_statements, control_requests, exceptions, description_approved; planned sources, fixture builds only); overdue pill above the line; quiet (ink-3) titles for "nothing yet" cards; the grid takes as many columns as cards; the note row (Info glyph on the nested fill); the stage tally ("7 of 9"); My K-1s; the notices info row; the unread dot; the user menu with scopes and role chips (DEC-346); T7-M (`mobile`): stacked 76 cards with chevrons, the vertical tracker, the collapsed team card, tab bar badges.
- `packages/ui`: `PortalToolbar`/`MobileHeader`/`PortalLayout` take `userMenu`; `PortalNavItem.countLabel`; the `MobileTabBar` draws count badges.
- `routes/portal/index.tsx`: `?scope=` and the 390 switch for Home.
- Fixtures: d's data from the artboard (Colorado, the reconnect and answer lines, the 1120-S line, the notice, recent threads), e's to-dos, stages and thread, a's recent threads, g (`luis-ferrante`, Thu Oct 22) and h (`marisol-vega`) homes and portal shells; the home handler answers by `scope_id`.

## Progress log
- 2026-10-25: built; `vitest run src/screens/POR-02` 26 passed (12 new for d, e, g, h, M and the acceptance); footing tests extended for g and h (Tessellate 26 / 3 / Sep 12). DEC-346 recorded.
- 2026-10-27 (S10 gap build, P-08-T26; no task file of its own and the TASK block is used up, so it is logged here, beside T23 which it depends on). The `J12-client-portal.spec.ts` steps walk in the fixture project on POR-01's own scenarios (`?st=`):
  - 2b: Tess signs in with the emailed code and her authenticator, then lands on POR-02 d.
  - 1e: an expired link is renewed by email.
  - 1g: the last wrong code shows Too many attempts.
  - Role union: Meera's home and her scopes. The account menu is closed before axe because the modal menu sets `aria-hidden` on `#root`.
  - The other projects keep these fixme until the sink mailbox reader exists (F-04-T22).
- Fixed a dev-only bug the 1e step found. `takeLinkFromFragment` and `takeInvitationFromFragment` ran inside `useState` initializers, which StrictMode calls twice; the second call found the fragment already cleared, so the emailed link or invitation token was lost under `make dev` and fixture mode. The pages now read the fragment purely and clear it in an effect (`useFragmentToken`).
- The harness keeps a path's `#fragment` after the added query, and the `tess-moreno` persona is added.
- Not done: j02 5 (Tess accepts and sees the Copperleaf first visit), the `por-01-sign-in` and `por-02-home` screen specs at 1400 and 390 with `assertInvariants`, and the full-stack nightly.
- Results: J12 fixture 6 passed, 2 fixme; portal, routes and POR-01 vitest pass except `link-contract.test.ts` rule 5 (ADM-04's links), which fails without this change.
