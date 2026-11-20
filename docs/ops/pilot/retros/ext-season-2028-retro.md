# Extension-season 2028 retro (Q-04-T231), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081, DEC-4100). The season is the autumn-2028 window, Fri Sep 1 – Fri Oct 20,
2028, in the plan's calendar (S48–S52); it is read on Fri Nov 20, 2026. No pilot firm is live
(DEC-1391), so every firm figure is zero or no data.

Acceptance: "The retro numbers reproduce from snapshots and logs and enter the capacity ledger."

## How to reproduce

    cd backend && uv run python -m abacus_tools.m12_pack \
      --firm 293fc3e7-be13-4767-ae6a-ce245b2dbda9 --code PF-X1 \
      --week 2028-09-04 --week 2028-09-11 --week 2028-09-18 --week 2028-09-25 \
      --week 2028-10-02 --week 2028-10-09 --week 2028-10-16 \
      --sprint 48 --sprint 49 --sprint 50 --sprint 51 --sprint 52

The pack reads the snapshots and logs only and prints each input's SHA-256. The read below ran
against the local database on 2026-11-20: support log `4a683fa1…`, escaped-defect log `a38878a5…`,
backlog `407308e1…`. A second read differs only where an input did.

## The retro's figures

| Figure | Value | Source |
|---|---|---|
| W4 portal activation, W5 PBC through the portal (seven weeks) | no data in any week (0 weeks live, 0 enrolments) | `pilot_metric_snapshots` |
| W6, W7 (seven weeks) | no data (0 enrolments with a baseline) | `pilot_metric_snapshots` |
| W8 | none recorded (PF-X1 dossier at shadow) | `docs/ops/go-live/PF-X1.md` |
| W9, W10 | not measured by the platform: F-09's partner and commercial signals | F-09 evidence pack |
| Support hours against the reserve | S48 0 of 37.50, S49 0 of 46.50, S50 0 of 43.50, S51 0 of 43.50, S52 0 of 18; SEV1/2/3 0; RK-07 does not fire | `docs/ops/pilot/support-hours.csv` against the reserve rows |
| Escaped defects dated Sep 4 – Oct 22, 2028 | none | `docs/quality/escaped-defects.md` |
| Flips in the window | 0 executed, 0 rolled back; the Sep 19 slot was the last in-window slot (Q-04-T216) and the five A-08 flips of Tue Oct 24 fall after the close, each with its rollback (Q-04-T230) | `docs/ops/windows/2028-10-16-deadline-week-watch.md` |
| Releases Oct 16-20 | none could run (P-29 gate refuses every instant without a hotfix) | same |

## What changes

Nothing in the calendar: with no live firm the season carries no load to learn from, and the
reserve rows stayed unused. The next read with real numbers is Season 3 support review 1
(Q-04-T260, S58) once the 2029 cohort's wave 1 is in shadow.
