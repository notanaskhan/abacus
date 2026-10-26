# Visual parity runbook (F-05-T61)

How to refresh the parity baselines, measure a template, lock it at its tier and hand the design
system on. Everything here runs on the gallery alone (`/components` on fixtures): no Docker, no
API, no database. The tiers and their tolerances are chapter 04 §9.3; the per-board record of every
lock, mask and deviation is `packages/ui/src/tokens/DECISIONS.md`.

## The pieces

| Piece           | Where                                                                            | What it holds                                                                                                                                       |
| --------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Handoff         | `$ACCRUED_HANDOFF_DIR` (read-only, never committed: the repo is public, D-DS-12) | the reference PNGs the baselines are cropped from                                                                                                   |
| Handoff version | `docs/design/HANDOFF_VERSION`                                                    | `<date> sha256:<hash of screen-index.json>`; baselines are keyed by it                                                                              |
| Manifest        | `docs/design/parity-manifest.json`                                               | one entry per board or part: `selector`, `page` (a screen page instead of the index), `source`, `sha256`, `crop`, `tier` A–D, `deviation`, `locked` |
| Baseline store  | `$ACCRUED_BASELINES_SOURCE/<handoff version>/`                                   | the crops and their `index.json` (hashes)                                                                                                           |
| Local baselines | `apps/web/.visual/parity.spec.ts/` (ignored by git)                              | what the parity spec compares against                                                                                                               |
| Tier A–C pixels | `apps/web/e2e/visual/parity.spec.ts`                                             | one test per manifest entry; report in `apps/web/parity-report/parity.json`                                                                         |
| Tier D geometry | `apps/web/e2e/visual/tier-d.spec.ts`                                             | exact computed sizes; needs no baseline and always blocks                                                                                           |
| Screen parity   | `apps/web/e2e/parity/screens.spec.ts` (`pnpm parity:screens`)                    | every screen artboard against its handoff crop, report-only (`parity-report/screens/`)                                                              |
| Accessibility   | `apps/web/e2e/a11y.spec.ts`                                                      | axe on every specimen and every overlay it opens; serious and critical block                                                                        |

The gate (parity.spec.ts): Tier A blocks; Tier B blocks once the entry is `locked: true`; Tier C
is report-only; an entry with a `deviation` is report-only and says why; Tier D always blocks.
Tolerances: A threshold 0.10 and 0.5 % of pixels, B 0.15 and 2 %, C 0.20 and 3 %
(`e2e/visual/support.ts`, calibrated in TASK-341).

Every render is the same: 1440 × 900 at DPR 2, light, reduced motion, `en-US`, America/Chicago,
the clock fixed at Mon Sep 14, 2026 9:24 AM CT, `?frame=1&static=1&contrast=reference`, fonts
loaded. Never compare a render made any other way.

## Before you start

1. `pnpm install --frozen-lockfile` and `cd backend && uv sync`.
2. Playwright's Chromium must match the pinned `@playwright/test` (`pnpm exec playwright install
chromium` from the lockfile's version). A mismatched browser is not a parity result: stop and
   fix the browser, never re-baseline over it.
3. `export ACCRUED_HANDOFF_DIR=…` (the handoff checkout) and `export ACCRUED_BASELINES_SOURCE=…`
   (a local directory; the `abacus-shared-design-baselines` bucket is not wired yet, Q-01).

## Refresh the baselines

Do this when the handoff changes (a new `screen-index.json`) or on a fresh machine.

1. If the handoff changed, update `docs/design/HANDOFF_VERSION` to the new date and
   `sha256:` of `screen-index.json`, and re-pin each manifest source:
   `cd backend && uv run python -m abacus_tools.parity.crop_handoff "$ACCRUED_HANDOFF_DIR" "$ACCRUED_BASELINES_SOURCE" --pin` (it writes under `<out>/<handoff version>/`).
   A source whose hash moved is a design change: read it before you accept it.
2. Crop: `pnpm -C apps/web visual:crop` (the same tool without `--pin`; `--only <key>` for one
   entry, `--skip-missing` while part of the handoff is absent).
3. Fetch into the local store: `pnpm -C apps/web visual:baselines`. It checks every file against
   `index.json` and removes crops the version does not name.
4. Run: `pnpm -C apps/web visual`. Read `apps/web/parity-report/parity.json` (artboard → diff % →
   tier → locked).

The regression screenshots (`pnpm visual:update`) are a different thing: the gallery against
itself at the pull request's base (`pnpm visual:ci`, F-05-T17). Never update them to make parity
pass.

## Add a template or a board to parity

1. The specimen: a board in `packages/ui/src/specimens/<id>.tsx`, registered in
   `packages/ui/src/specimens/index.ts` (its `id` is the gallery section id), drawing seed data only.
   A screen's artboards register in `apps/web/src/screens/gallery.tsx` with `registerScreen` and
   render at `/components/screens/<ID>?st=<letter>`; every artboard is a fixture scenario.
2. The manifest entry: key `<specimen id>.<board>`, the board's `selector` (frames use
   `[data-artboard="<id>"] [data-shell="app"]` and are shot at their exact box), the handoff
   `source`, its `sha256` (`--pin`), `crop` (the PNG's own 2x pixels, or `"window"` for a 1440 ×
   900 screen artboard: x 40–2840, y 40–1760) and `tier`.
3. Tier D: add the template's geometry to `tier-d.spec.ts` (pane widths, bar heights, row heights)
   from the numbers the handoff states and DECISIONS.md records.
4. Crop that entry (`--only <key>`), fetch, run `pnpm visual` and read its row.

## Lock a template

A template is locked when its boards block at their target tier (Tier B for frames and
specimens, under DEC-192's parity-tier reading; Tier A with masks only if that reading is ever
rejected).

1. Run the template's entries: `pnpm -C apps/web exec playwright test --project=visual
e2e/visual/parity.spec.ts -g "<specimen id>"` and `-g` the same on `tier-d.spec.ts`.
2. For each board in `parity.json`:
   - **≤ 2 % at Tier B** (≤ 0.5 % for Tier A): set `"locked": true` and drop its `deviation` if
     the deviation no longer measures (keep the words in DECISIONS.md).
   - **Over the tolerance with a recorded deviation** that is still true (a kit or screen still to
     come, synthetic page images): leave it unlocked, keep the deviation, and list it under "Not
     locked" with its measured diff.
   - **Over the tolerance because something moves** (a spinner, a presence avatar, an upload bar, a
     blank icon): the parity spec has no mask support yet (`data-parity-mask` marks the element,
     as TPL-02's dock does, but nothing reads it). Either add masking to `parity.spec.ts`
     (Playwright's `mask` on the `[data-parity-mask]` locators) in its own change, or leave the
     board unlocked with the reason recorded.
   - **Over the tolerance for no recorded reason**: it is a defect. Fix the template, never the
     baseline or the tolerance.
3. Tier D for every board of the template passes; `pnpm -C apps/web exec playwright test
e2e/a11y.spec.ts` is clean for its specimens.
4. Record the lock in `packages/ui/src/tokens/DECISIONS.md` under the lock task's heading: what is
   locked (boards, diff range), what is not and why (with the measured %), masks (or "None") and
   any Tier D rows added. Commit the manifest and DECISIONS.md together.
5. CI (`make ci-visual`) now blocks a regression of the locked boards.

Never lower a tolerance, delete a manifest entry or re-crop to make a board pass (AGENTS.md rule 13).

## Gallery how-to

- `make dev-fixtures`, then `/components` (every specimen, by kit), `/components/screens/<ID>`
  (one screen's artboards: `?st=` picks one, `&as=<persona>` overrides the viewer, `&static=1`
  freezes motion, `&frame=1` drops the gallery chrome).
- `?contrast=reference` draws the handoff's own ink ladder (parity renders); without it the AA ladder
  (DEC-11) the product ships.
- The side-by-side `/components/parity` page chapter 04 §9 describes is not built; compare by
  opening the crop in `$ACCRUED_BASELINES_SOURCE` next to the board, or read the diff images
  Playwright writes under `apps/web/test-results/` for a failed entry.
- The gallery never calls the API; a specimen that needs data takes it from the seed
  (`apps/web/src/fixtures/seed/`) or the kit's own fixtures, never invented numbers.

## Where F-05 stands (hand-off to F-06)

- **M5 lock (F-05-T49):** 49 frames locked at Tier B; T2a–e, T7-M, TPL-07-M, TPL-15c and j, TPL-11b
  not locked, with their measured diffs (DECISIONS.md).
- **Tier-2 lock (F-05-T60):** Tier D now covers every tier-2 template (T3, T5, T8, T9, TPL-02,
  TPL-03, TPL-05, TPL-08, TPL-09). The Tier B lock itself is **not yet measured**: the S10 session
  that wrote this ran without a working Chromium, every tier-2 entry still carries a recorded
  deviation (synthetic page images, the TPL-02 dock mask, monogram vendor tiles), and a board is
  locked only from a measured `parity.json`. The next session with a working browser follows "Lock
  a template" above for those nine and records the result under F-05-T60 in DECISIONS.md.
- **For F-06:** new templates follow "Add a template" and "Lock a template"; keep one heading per
  lock task in DECISIONS.md; Tier D rows go in as each template merges; the baselines bucket (Q-01)
  replaces the local `ACCRUED_BASELINES_SOURCE` when it is wired, with the same layout.
