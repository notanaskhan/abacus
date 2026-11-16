# T-07 parity and accessibility report (T-07-T31)

**Written 2026-11-16** on branch `t07-t31-parity-report` (TASK-8329). Screens: TXT-01, TXT-02, TXT-03, TXT-04. Targets: T-07 §5.5 (parity) and §5.6 (accessibility).

**Read this first.** Nothing here was measured by Playwright yet. The visual project, the screen parity report (`pnpm parity:screens`) and the axe specs run at the S47 end pass; until then every diff % is "not run", no lock is claimed and no axe result is claimed. The seven artboards the row names are the ones to lock at Tier C.

## 1. Parity: 25 artboards at Tier C, 7 to lock

Tier C: threshold 0.20, maxDiffPixelRatio 3 %. Status words: **reported**, **locked**, **not run**. TXT-03 and TXT-04 are built in fixture mode (T-07-T25, T-07-T26) as lean compositions; their geometry against the handoff (Tier D) is expected to differ until the T6 template chrome is composed.

| # | Artboard | Tier | Target | Diff % | Status |
|---|---|---|---|---|---|
| 1 | TXT-01 a | C | lock | — | not run |
| 2 | TXT-01 b | C | lock | — | not run |
| 3 | TXT-01 c | C | report-only | — | not run |
| 4 | TXT-01 d | C | lock | — | not run |
| 5 | TXT-01 d1 | C | report-only | — | not run |
| 6 | TXT-01 d2 | C | report-only | — | not run |
| 7 | TXT-01 d3 | C | report-only | — | not run |
| 8 | TXT-02 a | C | lock | — | not run |
| 9 | TXT-02 b | C | lock | — | not run |
| 10 | TXT-02 c | C | lock | — | not run |
| 11 | TXT-02 d | C | report-only | — | not run |
| 12 | TXT-02 e | C | lock | — | not run |
| 13 | TXT-02 f1 | C | report-only | — | not run |
| 14 | TXT-03 a | C | report-only | — | not run |
| 15 | TXT-03 b | C | report-only | — | not run |
| 16 | TXT-03 c | C | report-only | — | not run |
| 17 | TXT-03 d | C | report-only | — | not run |
| 18 | TXT-03 e | C | report-only | — | not run |
| 19 | TXT-04 a | C | report-only | — | not run |
| 20 | TXT-04 b | C | report-only | — | not run |
| 21 | TXT-04 c | C | report-only | — | not run |
| 22 | TXT-04 d | C | report-only | — | not run |
| 23 | TXT-04 e | C | report-only | — | not run |
| 24 | TXT-04 f | C | report-only | — | not built (composed frame) |
| 25 | TXT-04 c1 | C | report-only | — | not built (composed frame) |

## 2. Accessibility

axe on every scenario and open overlay, the keyboard suites (clause chips and passages, the calc tree, the release confirm, the sub-tabs), reduced-motion and forced-colours runs: **not run** (the end pass). The TXT-03 Release control carries its reason as its accessible name's description (`title`), and the TXT-04 Illinois card carries no figure (vitest, T-07-T26).

## 3. Gaps

- TXT-04 f and the composed c1 Approve values (L4) frame are not built.
- Tier D geometry needs the T6 template chrome on TXT-03 and TXT-04.
