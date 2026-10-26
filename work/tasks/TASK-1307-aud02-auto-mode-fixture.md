---
id: TASK-1307
title: AUD-02 f, the Auto mode switch and confirm in fixture mode (A-01-T31)
spec: docs/screens/AUD-02.md
acceptance_criteria: [A-01-T31]
risk_zone: green
status: in-review
epic: A-01
plan_key: A-01-T31
branch: s10-a01-auto-mode
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Build AUD-02 artboard f: the audit bar's Auto mode switch and its O3 confirm ("Turn on Auto
mode?" · Cancel · Turn on), with the server's refusal for a real firm, as a fixture scenario.
Live, the switch renders only when `/v1/me` reports `engagement_run.auto_mode`, and it writes the
`PUT /v1/engagements/{id}/auto-mode` shape P-10-T39 provides, so P-10-T39 turns it on with no
A-01 change.

## Plan
- **Seam** (`apps/web/src/domain/audits/mutations.ts`): `putAutoMode(engagementId, enabled)` names
  the not-yet-generated route on the generated `client` (precedent: `domain/portal/sign-in.ts`)
  with P-10's body `{enabled, confirmed: true}`; a 403/409 is a refusal by status.
  `useAutoMode(cockpit, initial)` reads the capability through `useCan`, holds the confirm's step
  (idle, asking, refused) and patches the cached cockpit on success.
- **Bar** (`AuditBar.tsx`): an `autoMode` option (null hides the switch, a value shows it) that
  overrides the projection's `auto_mode`; without the option the A-01-T06 rule stands.
- **Screen** (`screens/AUD-02`): the kit `ConfirmDialog` (not destructive) with `autoMode.confirm`
  copy; the refusal replaces its text (DV-12); OPENS f opens it asking.
- **Fixtures** (`fixtures/scenarios/AUD-02.ts`): f at 9:41 AM, Hannah Leclerc, the run rail, the
  capability, Auto mode off, a PUT that accepts; `autoModeRefused` (409).
- **Docs**: AUD-02.md row f, API row, `autoMode.refused`, DV-12, parity note; the manifest comment
  (frame owner A-01, route owner P-10); DEC-405.
- **Tests** (`AUD-02.test.tsx`): f's copy and the pressed switch; Cancel; Turn on's PUT body; the
  refusal; no switch live without the capability.
- **Rollback**: revert the commit; f leaves the scenario list and the bar is as before.

## Progress log
- 2026-10-26: planned and built. The P-10 epic's API table gives the body as
  `{enabled, confirmed: true}`, not `{auto_mode}`; the seam follows P-10. The kit's audit header
  flips its switch locally on click and re-syncs only when its `autoMode` prop changes, so the
  screen shows the switch pressed while the confirm is open and the prop falls back on Cancel,
  which turns it off again without a kit change. `tsc` reports 12 errors, all inside the generated
  `packages/api-client/src/core` (none in files this task touches). AUD-02.test.tsx 23 passed
  (5 new for f). Gap: an unexpected failure (not 403/409) closes the confirm silently; no copy
  exists for it.
