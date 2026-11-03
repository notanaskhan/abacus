# M14 ops retro, part N (Q-04-T088), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081). The window is autumn 2027 (Sep 1-Oct 20) in the plan's calendar; no pilot
firm is live (DEC-1391) and no production stack exists.

Acceptance: "The retro states each figure with its source and a decision on the fractional SRE."

## Figures

| Figure | Value | Source |
|---|---|---|
| Change failure rate in the window | **none to state**: no production change ran (0 releases), so the rate has no denominator | `deploy/production/release.json` (no digests); Q-04-T084, T085 |
| The build's nearest measure | `main`'s `ci` since 2026-10-30: 48 runs, 29 failed, 19 cancelled, **0 green**; the S24 and S25 batches merged with CI skipped | `docs/quality/integration-lane-2027-q3.md` (Q-03-T163) |
| Hotfix count in the window | **0**: no release record carries `hotfix`, and the gate refused every deadline-week promotion without one | release records; `docs/ops/windows/2027-10-11-deadline-week-watch.md` |
| Pages per week (RK-56) | **0** in each week of S25, and 0 SEV1/2 | `docs/ops/pilot/desk/s25-n-lane-on-call.md` (Q-04-T089) |
| N-lane support hours | 0 in S25 | `docs/ops/pilot/support-hours.csv` |

The zero page and hotfix figures say nothing about load: nothing was live to page about. RK-56 (founder
burnout) reads from the build itself in this period: one builder ran the S24 and S25 batches, the end
passes and this window's rehearsals in the same week.

## Decision on the fractional SRE (DEC-2082)
Keep ADR-100: a fractional SRE or managed partner is contracted before the first busy season in
which a pilot firm is live, as secondary SEV1/2 cover (Q-04-T096's terms: a read-only permission
set, no data-plane access, a sub-processor row, a runbook walkthrough). The synthetic window's zero
pages are no evidence against the need. The contract is triggered by the first real go-live
(`deploy/windows.yaml` gaining a firm with `real_data_since`), not by the calendar's Nov 2027; until
then no vendor is engaged and the founders' rota (`docs/ops/on-call.md`) is the cover plan.

## What only a live firm can show
A change failure rate over real releases, real hotfixes, and pages per week under load.
