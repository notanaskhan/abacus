---
id: TASK-910
title: SHL-03 firm menu - O1 tray, person card, capability-gated admin rows, sign-out (P-01-T08)
spec: SPEC-024
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: P-01
plan_key: P-01-T08
branch: TASK-910-shl03-firm-menu
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"SHL-03a-f pass their state tests and axe with no role-name comparison in the SPA." The firm pill
opens an O1 tray: firm rows (switching to another membership), the person card, Your profile,
the default office filter with its PUT, Notification preferences, Keyboard shortcuts, the admin
rows computed only from `/v1/me/capabilities.nav`, Sign out through `POST /v1/auth/sign-out`, and
the footer. Scenarios a–f, each with a test.

## What changed
- **Tray** `apps/web/src/shell/firm/FirmMenu.tsx`: a non-modal layer of the OverlayStack (Escape,
  press outside, roving ↑ ↓ Home End, → opens the office menu), `adminRows(nav)`,
  `cardLine(roles, job_title, office)`, `firmFacts(membership)` and a read-only profile drawer
  (O2). Copy in `shell/firm/copy.ts` (`FIRM_MENU`, `PROFILE`).
- **Layout** `legacy/Layout.tsx` mounts it in place of the F-05-T23 menu, which compared
  `firm_role` codes. Switching sets the tenant (`chooseTenant`); the menu resets every query and
  toasts. Sign out calls the generated `signOut` (P-01-T09's route, bearer), then the existing
  local sign-out and sign-in redirect; P-01-T11 replaces the latter with the BFF's hosted sign-in.
- **Session** `app-core/session.ts`: `nav` from the capabilities answer (fails closed to `{}`).
- **Fixtures**: the `/v1/me` v3 drafts of P-01-T07 are retired; `fixtures/seed/shell.ts` is typed
  with the generated `MeOut` (top-level `initials` and `job_title`), `MembershipOut.firm`,
  `OfficeOut` and `CapabilitiesOut`, and the four personas carry their firm-wide role with the
  backend's label. Scenarios a and f hold back Grace's sandbox membership (only e lists two
  firms); every scenario answers `POST /v1/auth/sign-out`.
- **Screen** `apps/web/src/screens/SHL-03/` (artboard, scenarios re-export, 18 tests); gallery
  `/components/screens/SHL-03?st=`; manifest SHL-03 `fixture`.
- **ESLint**: a screen may import its own scenarios from `fixtures/scenarios/<ID>` (the T07
  scenarios live there beside the seed).
- **packages/ui** `format.ts` `zoneName(tz)` ("Central Time"), with a test.
- **Docs**: `docs/screens/SHL-03.md`; DEC-142 (Q4 wordmark kept, card line, admin targets).

## Tests
- `screens/SHL-03/SHL-03.test.tsx`: SHL-03a–f, AC 2.1.1 (Escape, toggle, admin row navigation),
  AC 2.1.2 (nav only; no role code in the source), AC 2.1.3 (office PUT), AC 2.1.4 (switch
  toasts and refetches; the current firm is a no-op), AC 2.1.5 (profile drawer), AC 2.1.6 (sign
  out ends the server session first), the four card lines footing to the handoff, roving focus.
- `legacy/Layout.signout.test.tsx` now also asserts the `POST /v1/auth/sign-out` with the bearer
  token, and waits for the local sign-out, which follows it.
- `legacy/Layout.test.tsx`: the old menu's "‹person› · ‹firm›" line is gone; the two tests now
  find the person in the tray and the firm as its checked firm row.
- `fixtures/shell.foot.test.ts`, `fixtures/scenarios/SHL-03.test.ts`: retyped to the generated
  fields (`initials`, `job_title`, optional `firm`); same assertions.

## Commands
```
pnpm -C apps/web typecheck   # 0 errors in src; 12 pre-existing in packages/api-client/*.gen.ts
pnpm -C apps/web exec eslint <touched files>
pnpm -C apps/web exec vitest run src/screens src/fixtures src/legacy src/routes src/gallery src/app-core
pnpm -C packages/ui exec vitest run src/format.test.ts
make check-generated
```

## Progress log
- `2026-10-23` — Built and tested as above. Skipped: Tier C parity (P-01-T16 locks it), axe on the
  scenarios (P-01-T16), the 560 shortcuts dialog and ⌘ / (Keyboard shortcuts opens the interim Go…
  frame, which lists the same shortcuts).

## Gotchas and discoveries
- The fixture membership's `firm_name` is the short "Brightwater Hale", so frame a's firm row
  reads that where the handoff reads "Brightwater Hale LLP" (live seed: "Brightwater Hale LLP").
  No field carries a separate legal name; recorded under the contract's deviations.
- `pnpm -C apps/web typecheck` reports 12 `exactOptionalPropertyTypes` errors in the generated
  client core (`packages/api-client/src/{client,core}/*.gen.ts`), untouched by this task.
