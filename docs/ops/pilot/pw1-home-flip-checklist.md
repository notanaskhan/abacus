# PW1 flip checklist · HOME-01 lite (Tue Jun 1, 2027)

Owner: the builder (solo edition). Source: I-01-T14 (I-01 row; docs/screens/HOME-01.md), the
release windows (`docs/ops/release-windows.md`) and the flip guard (Q-04-T004).

HOME-01 lite turns on per PW1 firm by flipping `home.dashboard` for that tenant in the Tuesday
19:00–21:00 CT slot. Nothing in this list is a code change: each line is a check with its evidence.

## Before the slot (by Fri May 28, 2027)
- [ ] **Parity.** `ABACUS_VISUAL=1 pnpm exec playwright test e2e/visual/parity.spec.ts --grep home-01`
  reports a, a2, f and g under the Tier C threshold; their entries in
  `docs/design/parity-manifest.json` carry `"locked": true`.
- [ ] **Geometry.** `e2e/visual/tier-d-home.spec.ts` green: subbar 42, tiles 120 × 99 r14, pane
  header 46, activity rows 44, right column 420.
- [ ] **Accessibility and keyboard.** `e2e/home/home-mvp.spec.ts` green on every scenario.
- [ ] **Journeys.** j16 step 1 and j13 step 2 pass in compose and on staging with
  `assertInvariants` (INV-1 to INV-5).
- [ ] **Flag.** `home.dashboard` exists, default off, expiry after the next window's end (DEC-137);
  `python -m abacus_tools.flags` shows it off for every PW1 tenant.
- [ ] **Rollback.** RB-01 rollback path read: flag off returns the interim landing; no data
  migration to undo.

## In the slot
- [ ] `python -m abacus_tools.flip_guard` accepts the flip (window rules, approver rule waived in
  the solo edition, rollback named).
- [ ] Flip `home.dashboard` on for the PW1 tenant; record the ops request id.
- [ ] Sign in as a firm admin and as a staff member of that tenant: Home renders, the tiles' counts
  match `/v1/home`, and no client data shows for a role that may not see it.

## After
- [ ] The audit log names the flip and the person.
- [ ] Sentry and the SLO dashboard show no new HOME-01 errors for 24 hours.
