---
id: TASK-2472
title: Playwright part 1, the T-01 coordination slice, J14 steps 4 and 8, and the J12 TRI step (T-01-T29)
spec: SPEC-501
acceptance_criteria: [AC-1]  # All four specs pass full stack on staging before the Jul 27 shadow with INV-1, INV-3, INV-4 and INV-5 asserted and axe clean
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T29
branch: s19-t01-t29
created: 2026-11-01
updated: 2026-11-01
---

## Objective
T-01 §5 item 1: the nine named tests in `J06-1040-season.spec.ts`, `J14-firm-admin.spec.ts` and
`J12-client-portal.spec.ts`, each step with `axeStep` and `assertInvariants` (the harness).
Requested by the Sprint 21 session (it gates T-01-T46 and T-01-T47).

## Plan
- Register ADM-05, ADM-08, CLI-05 and TAX-09 in `fixtures/screen-scenarios.ts` so the fixture
  project walks the real routes on the screens' own scenarios (G-01-T16, DEC-457).
- Write the nine tests; the full stack and staging carry `fixme` with the owner of what is missing,
  hosted projects skip without their URL (the J14/J12 pattern).
- Fix what the walk finds.

## Progress log
- `2026-11-01` — Fixture project: 8 of 9 walk green (A3, A4, C-import, D1, D2 from approval given,
  agents-off, j14 4, j14 8). j12 TRI is fixme in both projects: POR-01 has no TRI step-up state for
  Claire (its two-step frame c is Tess's, by firm policy) and the full stack's codes come from the
  sink mailbox (F-04-T22). j06 D2's "Daniel approves" click has no fixture scenario; the fixture walk
  starts from approval given and says so in an annotation. The walk found two serious axe findings,
  fixed: ADM-05's evidence drawer wrapped `SheetRow`s in a `<dl>` (definition-list) and ADM-08's lock
  icon carried `aria-label` on a plain span (aria-prohibited-attr; now `role="img"`).
- Full fixture suite: 111 passed, 46 skipped, 3 failed (N01-inbox-files j16 6a, j16 10, j06 4),
  which fail the same way on unchanged main.
- Full stack and staging not walked: the T-01 slices and the fake CCH are not on the nightly stack
  (T-01-T23, T-01-T22 seed them; the nightly's slice list is F-04's), and staging has no URL yet
  (F-04-T28). The row's acceptance stays open until then.

## Handoff
- **Current state:** PR open, held for the batch. Row `partial`.
- **Exact next step:** add the T-01 slices to the nightly full-stack seed, drop the full-stack
  `fixme`s, and run on staging when `ABACUS_STAGING_URL` is set; a POR-01 TRI state for Claire is
  a design follow-up (no handoff frame).
