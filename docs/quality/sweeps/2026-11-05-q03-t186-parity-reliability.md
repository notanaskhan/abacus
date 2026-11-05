# Journey and parity reliability, 2027 Q4 (Q-03-T186)

Run Thu Nov 5, 2026 on main `596eba9cd` with I-01-T22 (#1221), on Playwright 1.64.1, the renderer
Q-03-T181 left owing a re-measure. The row is dated 2027 Q4 in the plan; under the solo amendment it
runs with the sprint that schedules it.

## Result: not met

Acceptance: "The quarantine holds 5 or fewer tests, none overdue, and locked screens report within
tier." The quarantine clause holds. The locked-screens clause does not.

| Clause | Result |
|---|---|
| Quarantine at most 5, none overdue | met: 0 in quarantine |
| Locked screens within tier | **not met**: of 215 measured rows, 141 within, 27 over, 47 unmeasured |
| Production-canary journeys | open: needs a deployed environment |

`npx playwright test --project=visual e2e/visual/parity.spec.ts` ran 504 tests: 466 passed, 38 failed,
1 skipped, in 54 minutes. Baselines came from `crop_handoff` at handoff version 2026-10-21.
`docs/design/parity-manifest.json`'s `tools` block now names 1.64.1, the renderer these numbers
came from.

**Cause not established.** There is no 1.63.0 run of the same tree to compare, so these rows may be
renderer drift, older screen drift or both. They are not from I-01-T22: its kit changes are scoped to
HOME-02, checked by re-running `t9b` (2.95 before and after).

## Locked rows over tier

| Row | Tier | Limit % | Diff % | Gate |
|---|---|---|---|---|
| `sig-01a.window` | C | 3.0 | 9.20 | report-only |
| `tax-03b.window` | C | 3.0 | 4.59 | report-only |
| `tax-03a.window` | C | 3.0 | 4.41 | report-only |
| `aud-31f.window` | C | 3.0 | 3.66 | deviation |
| `knw-03b.window` | C | 3.0 | 3.51 | report-only |
| `tax-02e.window` | C | 3.0 | 3.40 | report-only |
| `tax-02a.window` | C | 3.0 | 3.29 | report-only |
| `tpl-10a.window` | B | 2.0 | 3.26 | blocking |
| `tpl-10c.window` | B | 2.0 | 3.23 | blocking |
| `sig-01f.window` | C | 3.0 | 3.21 | report-only |
| `sig-01e.window` | C | 3.0 | 3.19 | report-only |
| `tpl-10d.window` | B | 2.0 | 3.04 | blocking |
| `knw-03a.window` | C | 3.0 | 3.01 | report-only |
| `tpl-11.a` | B | 2.0 | 2.56 | blocking |
| `tpl-07.b` | B | 2.0 | 2.51 | blocking |
| `tpl-18.a` | B | 2.0 | 2.47 | blocking |
| `tpl-06c.window` | B | 2.0 | 2.44 | blocking |
| `t7-client-portal.t7c` | B | 2.0 | 2.36 | blocking |
| `tpl-11.e` | B | 2.0 | 2.28 | blocking |
| `t7-client-portal.t7b` | B | 2.0 | 2.19 | blocking |
| `t10e.window` | B | 2.0 | 2.15 | blocking |
| `t7-client-portal.t7a` | B | 2.0 | 2.12 | blocking |
| `t10c.window` | B | 2.0 | 2.08 | blocking |
| `tpl-06e.window` | B | 2.0 | 2.06 | blocking |
| `tpl-11.c` | B | 2.0 | 2.06 | blocking |
| `tpl-18.d` | B | 2.0 | 2.05 | blocking |
| `t7-client-portal.t7e` | B | 2.0 | 2.03 | blocking |

## Locked rows with no measurement

47 rows report a size mismatch, so a lock on them proves nothing yet: the shot is the whole
frame while `crop: window` expects 2800 by 1720. ENG-04 (6), POR-05 (3), POR-06 (8), POR-13 (3), SHL-10 (3), SHL-11 (2), SHL-12 (3), SHL-16 (2), SIG-02 (3), TAX-09 (7), TAX-12 (7).

`aud-11f.window` is not cropped at all: its source PNG is 1520 by 1564, too small for the window crop.

## Other blocking and timed-out rows

- Not locked but over their blocking tier: `c-06-status-disc.done-15` 6.93, `c-06-status-disc.fail-15` 10.74, `c-06-status-disc.wait-15` 4.59, `c-06-status-disc.warn-15` 11.04, `t6a.control-bar` 1.35, `t6b.control-bar` 1.36, `t6c.control-bar` 1.35, `t6d.control-bar` 2.94, `t6e.control-bar` 1.35, `tpl-06a.control-bar` 1.18, `tpl-06b.control-bar` 1.18, `tpl-06c.control-bar` 1.16, `tpl-06d.control-bar` 1.39, `tpl-06e.control-bar` 2.10.
- `cli-05a` to `g` timed out: `[data-shell="app"]` never appeared in the artboard within 240 s. Not locked.

## Lock-list hygiene, proposed and not done

Re-crop or unlock the 47 unmeasured rows, then work the over-tier table. No lock, threshold or
mask was changed here (constitution rule 13).
