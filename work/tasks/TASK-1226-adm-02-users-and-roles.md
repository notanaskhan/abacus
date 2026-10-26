---
id: TASK-1226
title: ADM-02 Users & roles on the T12 frame — users table, role templates with CapabilityMatrix, invitations, invite and person drawers, after-season, pending invite, independence section (G-01-T10)
spec: SPEC-024
acceptance_criteria: [AC-3, AC-4, AC-8]
risk_zone: green
status: done
epic: G-01
plan_key: G-01-T10
branch: s8b-admin-kit
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Scenarios a–g pass with axe, the grid has text alternatives, and AY signs off fidelity."

## Plan
- `screens/ADM-02/` (index, users, templates, drawers, independence, model, copy, scenarios, test)
  on `SettingsLayout` (T12, `bare` and the new `wide` list body), reading through the generated
  client: `GET /v1/firm/staff` (filtered and unfiltered), `GET /v1/firm/role-templates`,
  `GET /v1/firm/staff/{id}`, offices, teams, the wall register, the firm's clients and members,
  `GET /v1/firm/independence/annual`; writes `POST …/invitations`, `PUT …/role`,
  `POST …/deactivate`, `PATCH /v1/firm/staff/{id}` (offshore). Segments and controls from `useCan`
  and `allowed_actions` (AC11.1). No backend, matrix or authz change.
- `packages/ui` (additive): `CapabilityMatrix` with text alternatives and a test; `TallyStrip`
  pill cards; `PaneHeader` `center`; `SettingsLayout` `wide`, `headerCenter`, `headerActions` with
  a test.
- Fixtures: the wall register (`firmWalls`), the person PATCH/role/deactivate handlers, the list
  refused to non-admins (DEC-286), capabilities per persona in the ADM-02 scenarios.
- Route `/settings/people` behind `firm_settings.v2` with its search params; manifest keeps ADM-02
  `planned` with its path (DEC-195); gallery entry for the e2e/axe harness.
- Rollback: revert the commit; nothing persistent.

## Progress log
- 2026-10-25: built on `s8b-admin-kit`. 15 screen tests (a–g, the Office filter, search, the
  role change and deactivation with their confirms, the offshore refusal, not-allowed) pass.
  DEC-353 records the as-built choices; `docs/screens/ADM-02.md` updated to match.
- Deferred: the SHL-03 self-confirm dialog (AC6.1) waits for G-01-T13 (the confirm route is a 501
  stub and the statements are firm content not yet registered); Independence shows live once T13
  answers the year's read. Hard-limit locks in the grid need `role-templates.yaml` to declare them
  (protected; core lane). The Playwright spec with axe (`e2e/screens/adm-02.spec.ts`) is
  G-01-T16's; the gallery entry is ready. The `/admin/people` redirect waits for the staging walk
  (T17 retires the legacy screen).
- Shared machine note: under load (load average ~30) `router.test.tsx` and the gallery index test
  time out at their 5 s budget and pass alone; not this change.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-353 | ADM-02's segments, deferrals, data gaps, writes, copy and manifest status | No |
- 2026-10-26 (S10 code gap, branch `s10-g01-t10-selfconfirm`): the SHL-03 profile drawer's
  annual independence self-confirmation (AC6.1), now that G-01-T13's routes are live: the row
  "Annual independence confirmation · ‹year› · Confirm…", a dialog with the firm's published
  statement as written, Confirm, and Decline with a required note; the confirmed or declined date
  afterwards. `docs/screens/ADM-02.md` updated (DEC-353's wait is over). Tests at the end of the
  run (not yet, confirm, decline needs a note, no statement).
