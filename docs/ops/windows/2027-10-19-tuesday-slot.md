# Tuesday slot, Oct 19, 2027 (Q-04-T092), rehearsed on PF-X1

**Synthetic.** No pilot firm is live (DEC-1391), so this row runs on the synthetic test firm PF-X1
(Brightwater Hale, DEC-1530) and is reported as synthetic (DEC-2081). Nothing was promoted and no
flag was flipped: there is no production stack yet, and the slot is in the plan's calendar (autumn
2027), not today's.

Acceptance: "The flip is recorded, windows.yaml shows the window closed and the Oct 21 promotion
runs on the Thursday slot."

## The slot, the close and the first Thursday train under the real gate

`python -m abacus_tools.window_rehearsal --firm PF-X1 --live-since 2027-08-02 --at
2027-10-19T19:05:00-05:00 --at 2027-10-20T23:59:00-05:00 --at 2027-10-21T19:05:00-05:00` runs
`release.window_gate` over `deploy/windows.yaml`, in memory only (the file keeps PF-X1 synthetic).

| Instant (CT) | Window | Deadline week | Mini-freeze | Tuesday slot | Flip slot | No window facts | defect_only + rollback | + hotfix |
|---|---|---|---|---|---|---|---|---|
| 2027-10-19T19:05:00-05:00 | autumn-2027 | - | - | yes | yes | refused: window_mode_missing, rollback_missing | promotes | promotes |
| 2027-10-20T23:59:00-05:00 | autumn-2027 | - | - | no | no | refused: window_mode_missing, rollback_missing, outside_the_tuesday_slot | refused: outside_the_tuesday_slot | promotes |
| 2027-10-21T19:05:00-05:00 | - | - | - | no | yes | promotes | promotes | promotes |

- **The flip.** `ledger.tb_mapping` (A-03, Dec-YE planning) is the slot's one planned flip. On PF-X1
  it is a synthetic firm's flag state, recorded here: Oct 19 19:05 CT is in the Tuesday and flip
  slots, where a `defect_only` record with a rollback promotes. A real firm's flip carries an
  approver and the rollback (flag off) in `deploy/windows.yaml`.
- **The window closes.** `deploy/windows.yaml` ends `autumn-2027` on 2027-10-20: at 23:59 on Oct 20
  the window still holds (only a hotfix promotes); on Oct 21 no window applies.
- **Oct 21.** The first Thursday train after the window promotes every record, so weekly
  promotion resumes. No `windows.yaml` entry needs retiring: the window's end date retires it.

## What only a live firm can show
- The flip on a real tenant, its approvals, and the closing note by 21:00 CT.
- The Oct 21 production promotion itself (`make release-pr SHA=...`).
