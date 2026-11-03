# Tuesday slot, Oct 5, 2027 (Q-04-T084), rehearsed on PF-X1

**Synthetic.** No pilot firm is live (DEC-1391), so this row runs on the synthetic test firm PF-X1
(Brightwater Hale, DEC-1530) and is reported as synthetic (DEC-2081). Nothing was promoted and no
flag was flipped: there is no production stack yet (`deploy/production/release.json` holds no
digests), and the slot is in the plan's calendar (autumn 2027), not today's.

Acceptance: "The release record shows window_mode and rollback, and every flip has both approvals."

## The slot under the real gate

`python -m abacus_tools.window_rehearsal --firm PF-X1 --live-since 2027-08-02 --at ...` runs
`release.window_gate` over `deploy/windows.yaml` with PF-X1 treated as live from Aug 2, 2027, in
memory only (the file keeps it synthetic). The three records are rehearsal records with zero
digests: one with no window facts, one `defect_only` with a rollback (RB-16), and the same with a
hotfix.

| Instant (CT) | Window | Deadline week | Mini-freeze | Tuesday slot | Flip slot | No window facts | defect_only + rollback | + hotfix |
|---|---|---|---|---|---|---|---|---|
| 2027-10-05T14:59:00-05:00 | autumn-2027 | - | - | no | no | refused: window_mode_missing, rollback_missing, outside_the_tuesday_slot | refused: outside_the_tuesday_slot | promotes |
| 2027-10-05T19:05:00-05:00 | autumn-2027 | - | - | yes | yes | refused: window_mode_missing, rollback_missing | promotes | promotes |
| 2027-10-05T19:59:00-05:00 | autumn-2027 | - | - | yes | yes | refused: window_mode_missing, rollback_missing | promotes | promotes |
| 2027-10-06T19:05:00-05:00 | autumn-2027 | - | - | no | no | refused: window_mode_missing, rollback_missing, outside_the_tuesday_slot | refused: outside_the_tuesday_slot | promotes |

- **window_mode and rollback.** A release record without them is refused in the window
  (`window_mode_missing`, `rollback_missing`); `defect_only` with a rollback promotes in the slot
  and nowhere else that week. Oct 5 is in neither a mini-freeze (Oct 8-15) nor a deadline week.
- **The migrate step** waits for 20:00 CT (`migrate_not_before`: 2027-10-05 20:00-05:00), and a
  contract operation in the release's migrations would be refused in the window (Q-03-T081).
- **Flips.** `make flag-calendar` lists 85 flags and none with a window flip planned for Oct 5
  (0 rows in its window column), so there is no flip to carry two approvals. A planned flip would
  need an approver and a rollback even on PF-X1 (`deploy/windows.yaml`, DEC-1530).

## What only a live firm can show
- A real release record for the slot (`make release-pr SHA=...`) and its closing note by 21:00 CT.
- RB-16 §6's checks before the slot: staging journeys green within 24 hours, the shadow run clean,
  the canary green, then production journeys and the canary re-checked after it.
- Both founders' approvals on an actual flip.
