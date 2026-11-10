---
id: TASK-6623
title: "P-09-T18: SHL-13 and WB-09 parity (crops, Tier D, Tier C locks) and accessibility"
spec: SPEC-648
acceptance_criteria: [AC-9]
risk_zone: green
status: in-review
branch: s34-p09-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-09-T18
---

## Objective
Tier D passes, the locked artboards stay under 3%, axe reports zero serious or critical issues
and the keyboard and reduced-motion suites pass.

## Built
- Gallery (`screens/gallery.tsx`): `SHL-13?st=board` (the eight 330 × 733 docks at x 24/378/732/1086,
  y 60/877, each a `RunPane` on its fixture run), `SHL-13?st=F` (the AUD-02 cockpit at 9:41 with run
  #4127 open in the dock), `WB-09?st=a|a2|a3|a4|b|c|d|e` (the trace drawer on the E0 runs; a3/a4
  open on Records read / Writes & approvals, e holds the trace unanswered). All on
  `fixtures/scenarios/SHL-13.ts`: the E0 seed, the fixture runs' routes (`agentRunHandlers`, first
  mounted here) and `agent_runtime.v2`, `agent_dock.enabled`, `run_trace.enabled` on.
- Small seams: `AuditCockpitPage` `initial.run`; `TraceDrawer` `initialView`.
- Manifest (`docs/design/parity-manifest.json`): `shl-13x.dock-1…8` (crops on the 2× board,
  report-only), `shl-13.window` (locked), `wb-09{a,a2,a3,a4,b,c,d,e}.window` (a, b, c locked; a2
  report-only with its deviation). Masks: spinners, shimmer, live dot.
- `e2e/visual/tier-d-agents.spec.ts`: dock 330 × 733 radius 12, header 46, "Agent" 14.5/500,
  composer 38 on nested, user bubble 14; drawer 480 at 10/10/10 radius 14, header 46, Segmented 28.
- `e2e/screens/agents-a11y.spec.ts`: axe AA on every state; reduced motion (no running animation);
  tool cards as disclosure buttons; 1–9 on the ask card; Segmented arrows; the drawer modal with
  focus kept inside.

## Progress log
- 2026-11-10: built; parity, Tier D and axe run at the S34 end pass. The locks (SHL-13·F, WB-09a/b/c)
  are set on the plan's word; any that measures over 3% at the end pass becomes report-only with
  its measured figure as the deviation (the A-01-T33 rule), in the fix round.
- Partial:
  - SHL-13·9 (dock beside a sheet, Cole Hart BH-FS-430) and ·10 (thumbs-down reason picker) have no
    gallery state: no sheet host or reason picker fixture exists. No manifest entry (P-09 §5.4
    already holds them report-only).
  - TPL-02's dock masks stay: the F-05 specimen in packages/ui draws a placeholder thread and cannot
    mount the web's `RunPane`; dropping the mask needs the specimen rebuilt on the C-12 run kit
    (follow-up for F-05's specimen owner). A-01-T33 drops the AUD-02 dock masks instead, where the
    cockpit renders the real dock.
  - Keyboard: Escape-closes-topmost and focus return need a host opener; the gallery's drawer has
    none (onClose is a no-op), so the suite checks aria-modal and the focus trap only. The
    journeys (P-09-T19) cover close-and-return from the AUD-02 host.
  - Docks 3 and 4 both read run #4127 at 9:41 (the fixture has one running run); 4's scroll
    position (the decision card) differs from the board, report-only.
- 2026-11-10 (measured, S34 partials pass): visual project on main 799a6e5bc with baselines cropped
  from the handoff. Tier D 13/13 (eight docks, the user bubble, WB-09 a–d). Tier C: SHL-13·F
  (`shl-13.window`) 5.01 %, docks 1–8 2.17 / 5.99 / 6.49 / 6.20 / 5.41 / 6.74 / 3.32 / 3.39.
  WB-09 is not measurable: the gallery draws the drawer pinned 10 px inside the 1440 × 900 viewport
  (480 × 880) and the handoff draws it inside the 1400 × 860 window over WB-01 (480 × 840), so every
  WB-09 shot is a size mismatch. Per the A-01-T33 rule, `shl-13.window` and `wb-09{a,b,c}.window`
  drop `locked` and carry the measured figure or the reason as their deviation. Follow-up: a WB-09
  gallery frame that draws the WB-01 window behind the drawer, then re-measure and lock a, b, c.
