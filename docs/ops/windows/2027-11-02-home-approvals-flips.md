# home.approvals flips, Nov 2 and Nov 9, 2027 (Q-04-T097), rehearsed on PF-X1

**Synthetic.** No pilot firm is live (DEC-1391), so this row runs on the synthetic test firm PF-X1
(Brightwater Hale, DEC-1530) and is reported as synthetic (DEC-2081). Nothing was promoted and no
flag was flipped: there is no production stack yet, and the slots are in the plan's calendar
(autumn 2027), not today's.

Acceptance: "Both flips are recorded with rollback refs and the flag's retirement is booked for the
Dec bundle."

## The two slots and the retirement's

`python -m abacus_tools.window_rehearsal --firm PF-X1 --live-since 2027-08-02 --at
2027-11-02T19:05:00-05:00 --at 2027-11-09T19:05:00-06:00 --at 2027-12-14T19:05:00-06:00` runs
`release.window_gate` over `deploy/windows.yaml`, in memory only (the file keeps PF-X1 synthetic).
Clocks change on Nov 7, 2027, so Nov 2 is CDT and Nov 9 and Dec 14 are CST.

| Instant (CT) | Window | Deadline week | Mini-freeze | Tuesday slot | Flip slot | No window facts | defect_only + rollback | + hotfix |
|---|---|---|---|---|---|---|---|---|
| 2027-11-02T19:05:00-05:00 | - | - | - | yes | yes | promotes | promotes | promotes |
| 2027-11-09T19:05:00-06:00 | - | - | - | yes | yes | promotes | promotes | promotes |
| 2027-12-14T19:05:00-06:00 | - | - | - | yes | yes | promotes | promotes | promotes |

## The flips

| Flip | Firm | Slot | Rollback ref |
|---|---|---|---|
| 1 | PF-X1 (synthetic), the first wave's slot | Tue Nov 2, 2027, 19:05 CT | RB-48 §4: `home.approvals` off for the firm; gates stay with their owners |
| 2 | PF-X1 (synthetic), the second wave's slot | Tue Nov 9, 2027, 19:05 CT | RB-48 §4: the same |

Both instants sit in the Tuesday and flip slots, so a flip recorded there passes the gate. A real
firm's flip carries its approver and the rollback in the ops request (RB-48 §2).

## The retirement

Booked in `docs/plan/status/flag-renewals-2027.md`:

- **Renew first.** `home.approvals` expires 2027-04-28, before either flip. It must be renewed to
  Dec 30, 2027, or the flips cannot run.
- **Retire in the Dec 14, 2027 train**, the Dec 14–17 protected bundle, once the flag is on for every
  live firm.

## What only a live firm can show
- The flips on a real tenant, their approvals and RB-48 §3's verification.
- The audit half of HOME-02 walked on staging (I-01-T22 keeps that open).
- The retirement itself in the Dec 14 train.
