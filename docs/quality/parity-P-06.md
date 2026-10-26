# P-06 parity and accessibility report (P-06-T26)

**Written 2026-10-26** on branch `s10-p06-closeout` (TASK-1310). Screens: BND-01, BND-02, SHL-14, SHL-20. Targets: P-06 §5.5 (parity) and §5.6 (accessibility); DoD items 2 and 3 (§10). Decision: DEC-408.

**Read this first.** Nothing in this report was measured by Playwright. The visual project (`e2e/visual/`), the screen parity report (`e2e/parity/screens.spec.ts`, `pnpm parity:screens`) and the axe specs (`e2e/screens/*.spec.ts`) were **not run**: the cached chromium does not match the pinned Playwright here, and this session ran no browser. Every diff % below is "not run", no lock is claimed, and no axe result is claimed. The keyboard suites are vitest and did run (§3).

## 1. Parity: 23 artboards at Tier C

The handoff has 24 artboards; 23 are built (P-06 §0). SHL-14 c (sample-driven bulk) is deferred to A-03 and recorded in `routes/manifest/shl.ts`, not missing.

Tier C: threshold 0.20, maxDiffPixelRatio 3 %. Status words: **reported** (measured, report-only), **locked** (measured and blocking), **not run** (no measurement exists).

| # | Artboard | Viewer · clock | Tier | Target (§5.5) | Diff % | Status | Mask |
|---|---|---|---|---|---|---|---|
| 1 | BND-01 a Default | Grace Holloway · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 2 | BND-01 b No client activity in 30 days | Grace Holloway · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 3 | BND-01 c Unpublished row | Remy Vidal · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 4 | BND-01 d Season empty TY2026 | Grace Holloway · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 5 | BND-01 e Loading | Grace Holloway · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | skeleton pulse |
| 6 | BND-02 a Published · 2 open | Kevin Osei · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | "Uploading" spinner |
| 7 | BND-02 b Draft · TY2026 roll-forward | Kevin Osei · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 8 | BND-02 c Complete | Kevin Osei · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 9 | BND-02 d Overdue · Thornbury | Kevin Osei · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 10 | BND-02 e Ignored · Thornbury | Kevin Osei · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 11 | BND-02 f Visibility off | Kevin Osei · Sep 14, 9:24 AM | C | lock at end of S10 | — | not run | — |
| 12 | BND-02 g Upload needs review (R2) | Kevin Osei · Sep 14, 9:31 AM | C | lock at end of S10 | — | not run | — |
| 13 | SHL-14 a New | Marcus Delaney · Sep 14, 9:41 AM | C | report-only | — | not run | — |
| 14 | SHL-14 b Edit · third party | Marcus Delaney · Sep 14, 9:41 AM | C | report-only | — | not run | — |
| 15 | SHL-14 d Close variant | Raj Malhotra · Sep 14, 9:41 AM | C | report-only | — | not run | — |
| 16 | SHL-14 e Validation | Marcus Delaney · Sep 14, 9:41 AM | C | report-only | — | not run | — |
| 17 | SHL-14 f Draft by the agent (R2) | Cole Hart · Sep 24, 10:58 AM | C | report-only | — | not run | — |
| 18 | SHL-20 a Flagged | Cole Hart · Sep 26, 10:14 AM | C | report-only | — | not run | — |
| 19 | SHL-20 b Draft follow-up | Cole Hart · Sep 26, 10:16 AM | C | report-only | — | not run | — |
| 20 | SHL-20 c Rerunning | Cole Hart · Sep 28, 9:05 AM | C | report-only | — | not run | skeleton pulse, spinner |
| 21 | SHL-20 d Passed | Cole Hart · Sep 28, 9:05 AM | C | report-only | — | not run | — |
| 22 | SHL-20 e Not screened | Cole Hart · Sep 25 | C | report-only | — | not run | — |
| 23 | SHL-20 f Feedback | Cole Hart · Sep 26, 10:14 AM | C | report-only | — | not run | — |
| — | SHL-14 c Sample-driven bulk | — | — | deferred to A-03 | — | recorded, not built | — |

Reason for every "not run": Playwright visual project not run in this environment; baselines to capture at the batch merge.

### BND-01 and BND-02 Tier C locks: pending measurement

P-06 §5.5 locks BND-01 and BND-02 at Tier C at the end of S10. They are **not locked**: a lock needs a measured run under the threshold first. Three things stand between today and that lock (DEC-408):

1. **No baseline on disk.** The handoff PNGs are fetched into the git-ignored `.visual/` by `pnpm visual:baselines`; `docs/design/parity-manifest.json` has no `bnd-01*`, `bnd-02*`, `shl-14*` or `shl-20*` window entries yet, so the harness would report every one of these rows as unmeasured, never passed. The crop entries (`python -m abacus_tools.parity.crop_handoff --pin`) need `$ACCRUED_HANDOFF_DIR`.
2. **BND-02 is `planned` in the route registry** (`routes/manifest/bnd.ts`), so `screenRows()` leaves all seven BND-02 artboards out of the screen report. It turns `fixture` when CLI-01's "open binder" link is wired (`docs/screens/BND-02.md`, Open gaps).
3. **A Tier C lock blocks nothing in the harness today.** `gateOf()` in `e2e/parity/screen-rows.ts` blocks Tier A and D always and Tier B once locked; Tier C is report-only even when locked (asserted in `src/routes/screen-parity.test.ts`). §5.5's "blocking thereafter" needs that rule changed when the first Tier C lock is measured. Not changed here (F-04-T33 owns the harness).

The contracts' Parity tables (`docs/screens/<ID>.md`) now say "not run" with the reason and "pending its first measured run". None of them uses the word the harness parses as a lock, so no row reads locked by accident (BND-01's note "locked (blocking) at the end of S10" used to).

### Tier D on the host templates

| Host | Values (§5.5) | Tier D row in `e2e/visual/tier-d.spec.ts` | Status |
|---|---|---|---|
| Shell (toolbar 46, subbar 42, pane header 46 with a 14.5/500 title) | as listed | yes ("tier D: the shell") | not run |
| Pills 21/19/18, radius 12 | as listed | yes ("tier D: computed styles") | not run |
| T1 IndexList (rows 38/44) | rows 38/44 | no row yet | not measured |
| T2 RecordCockpit (rail 330, canvas 696, dock 330) | as listed | yes ("tier D: T2 record cockpit") | not run |
| O1 C-34 ScreeningCard 420 | card 420, radius 12, header 44 | no row yet | not measured |
| O2 drawer 480 | drawer 480 | no row yet | not measured |
| O3 sheet 500 | sheet 500 | no row yet | not measured |

## 2. axe

axe runs only in Playwright here (`@axe-core/playwright` is the allowlisted package; `axe-core` is not imported directly, and no vitest axe helper exists). This task did not run it. **Result: not run; zero serious or critical findings is not claimed.**

Specs that hold the check (each asserts zero serious or critical findings inside the artboard):

| Spec | Artboards | Change in P-06-T26 |
|---|---|---|
| `e2e/screens/BND-01.spec.ts` | a, b, c, d, e | b added |
| `e2e/screens/BND-02.spec.ts` | a–g | g added |
| `e2e/screens/SHL-14.spec.ts` | a, b, d, e, f | none |
| `e2e/screens/SHL-20.spec.ts` | a–f, with the O3 sheet (b) and "Why?" (f) | new |

Run at the batch merge: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/BND-01.spec.ts e2e/screens/BND-02.spec.ts e2e/screens/SHL-14.spec.ts e2e/screens/SHL-20.spec.ts`, then record the counts here.

## 3. Keyboard suites (vitest, run)

`pnpm -C apps/web exec vitest run src/screens/BND-01 src/screens/BND-02 src/screens/SHL-14 src/screens/SHL-20 src/routes/screen-parity.test.ts`: **9 files, 124 tests, all passed** (27 new keyboard tests plus the existing 97). jsdom does not move focus on Tab, so each suite reads the tab order from the DOM (`src/testing/keyboard.ts`) and checks that no positive tabindex exists.

| Suite | Tests | What it proves |
|---|---|---|
| `BND-01.keyboard.test.tsx` | 6 | Tab runs filters → tiles → search → Send reminders… → New binder… → row menus; tiles are buttons with `aria-pressed`; Escape closes the row menu, the Unpublish dialog, the New binder sheet and the follow-up sheet, and focus returns to the opener; nothing is sent |
| `BND-02.keyboard.test.tsx` | 9 | Tab runs rail → canvas → dock; Publish to client… and the dock's Accept and Return… are reachable; a row is selected through its title button (`aria-pressed`); the Eye is a toggle with `aria-pressed`; Escape closes the row menu, Publish, Preview as client, Return to client, the follow-up sheet and the ReturnDialog, with focus back on the opener |
| `SHL-14.keyboard.test.tsx` | 6 | Focus moves into the drawer; Tab runs tabs → fields → Save draft → Save & send last; the tabs are a tablist with a roving tabindex and arrow keys; the due-date error is linked to its field (`aria-invalid`, `aria-describedby`); Escape closes a pristine drawer with focus back on the opener; a dirty one asks "Discard changes?" first |
| `SHL-20.keyboard.test.tsx` | 6 | Escape closes the card and focus returns to the screening chip, as ✕ does; Return… and "Why?" close on Escape without closing the card; Tab reaches View, Return… and Draft follow-up; "Why?" is a radio group whose Send waits for a reason; the running card is `aria-busy` with a polite line |

**Defect found and fixed (ED-090).** The SHL-20 card did not close on Escape, and ✕ dropped focus to the page instead of the chip (§5.6). `src/screens/SHL-20/index.tsx` now closes the card on Escape from anywhere in its frame and gives focus back to the chip; overlays the card opens are portalled and keep their own Escape.

## 4. §5.6 items not met or not measured

| §5.6 item | State | Owner |
|---|---|---|
| BND-01 table: Space selects a row, Enter opens it | **Not met.** T1 `IndexList` rows are not focusable and have no key handler; a row is selected by mouse only. The row's ··· menu and (on the route) its Open button are reachable. Selecting one binder for "Send reminder…" is mouse-only; "Send reminders…" over the binders in view is reachable | F-05 T1 kit (`ui-kit-component`); DEC-408 |
| Bulk bar announced politely ("1 selected") | Not built: DV-15 replaced the bulk bar with the pane header's action | DEC-222 |
| Eye: label "Visible to client", helper by `aria-describedby` | Partly: a toggle with `aria-pressed`, labelled "‹title›: visible to client" or "‹title›: hidden from client"; the "Internal only" helper is not linked by `aria-describedby` | BND-02 follow-up |
| 24 px target size | Not measured. The row screening glyph is 18 px and the Eye 22 px; whether the spacing exception holds is axe's `target-size` call in Playwright | at the axe run |
| Forced colours keep pane edges and focus rings; reduced motion stops pulse and spinner | Not measured (Playwright, `reducedMotion: "reduce"` is set in the specs) | at the axe run |

## 5. To do at the batch merge

1. Pin the 23 crops in `docs/design/parity-manifest.json` and fetch the baselines.
2. Run the four axe specs and `pnpm parity:screens`; record diff % and axe counts in §1 and §2.
3. Flip BND-02 to `fixture` when its entry link exists, then lock BND-01 and BND-02 at Tier C in their contracts (`C (locked)`) if they measure under 3 %, and decide the harness rule for a locked Tier C (DEC-408).
