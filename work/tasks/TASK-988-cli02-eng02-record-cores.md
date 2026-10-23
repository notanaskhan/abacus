---
id: TASK-988
title: CLI-02 client record core and ENG-02 engagement record core on T2, without the dock (P-07-T19, P-07-T20)
spec: SPEC-321
acceptance_criteria: [AC-7, AC-8]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T19; P-07-T20
branch: s6-cli02-eng02
created: 2026-10-23
updated: 2026-10-23
---

## Objective
P-07-T19 and P-07-T20 in one change. CLI-02 at `/clients/$clientId` behind `clients.v2` on T2
over the live clients contract (record, overview, relationships, PATCH, TIN reveal); ENG-02 at
`/engagements/$engagementId` behind `engagements.v2` on T2 without the dock over the v2 record
projection (stub until P-07-T15). Every state this task builds is a fixture scenario with a test
and an axe run.

Acceptance (P-07-T19): "Scenarios a to f pass with axe, the reveal announces and re-masks, and
production hides the dock and the responsiveness card." Acceptance (P-07-T20): "The G3 banner
clears only after a recorded letter dated after the acceptance decision, and every state passes
axe."

## What changed
- **CLI-02** `apps/web/src/screens/CLI-02/` (`index.tsx`, `copy.ts`, `scenarios.ts`,
  `CLI-02.test.tsx`): the client subbar (kind pill from the primary entity, risk, partner and
  office), seven tabs (Overview, Engagements and Relationships in-screen; Contacts & access, Tax
  profile, Files and Messages planned and hidden in production; Activity hidden until P-07-T61),
  the Summary rail (name block with the "n active engagements ⌄" menu, stat rows, Details with the
  masked TIN and Reveal, Team with the relationship-partner picker that PATCHes with
  `seen_version`, Client Portal, Links), and the overview cards from the sections the server
  returns (Active work, the K-1 table with the computed Schedule K total, Waiting on client,
  Client responsiveness, Key dates, Recent activity). A 404 renders the walled state (INV-3).
- **Domain** `apps/web/src/domain/clients/record.ts` (record, overview, staff names, PATCH,
  reveal, section and stat helpers, bigint sums) and `MaskedTin.tsx` (reason dialog, the value
  for `remask_after_seconds`, a polite live region, re-mask, focus back to the button).
- **ENG-02** `apps/web/src/screens/ENG-02/`: the engagement subbar, tabs (Overview, Work items,
  Letter & terms; Team planned), the Summary rail from `bands`, the gate rows
  (`domain/engagements/GateBlock.tsx`), the prospect and G3 banners, the work items, the Letter &
  terms record-mode card and the Record signed letter sheet (O3) over
  `PUT /v1/engagements/{id}/letter/record`; d disables every action.
- **Fixtures** `fixtures/seed/client-records.ts`, `handlers/client-record.ts`,
  `scenarios/CLI-02.ts` (a, a2, b, c, e, f), `client-records.foot.test.ts`;
  `seed/engagement-records.ts`, `handlers/engagement-record.ts`, `scenarios/ENG-02.ts` (b, c, d,
  e, prospect).
- **Routes** `routes/firm/clients.tsx` (CLI-02 behind `clients.v2`; CLI-01's row and its Open item
  now open CLI-02), `routes/firm/engagements.tsx` (ENG-02 behind `engagements.v2`); the gallery
  registers both; `e2e/screens/CLI-02.spec.ts` and `ENG-02.spec.ts` run every scenario with axe.
- **Contracts** `docs/screens/CLI-02.md` and `ENG-02.md`: states, deviations, the sheet's
  strings, parity rows. Decision DEC-195.

## Not built, and why
- CLI-02 d (the agent dock answering) and the dock thread on a–e: no API carries the dock thread
  until P-09-T09's AgentDockHost, and screens read data only through the generated client.
- ENG-02 a, f, g, the status menu (On hold…), the Team tab host and the gear: P-07-T28 and
  P-07-T15 (the hold route).
- Manifest entries CLI-02 and ENG-02 stay `planned` (as BND-02 does): `to.<ID>()` carries the
  manifest's names, which the production dist must not hold, so the links are wired in
  `routes/firm` (DEC-195).

## Progress log
- 2026-10-23: built and tested; vitest, typecheck, lint, Playwright with axe for every scenario,
  `make check-fast`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-195 | CLI-02 and ENG-02 cores: what the generic sections carry, the gate lines, the manifest status | no |
