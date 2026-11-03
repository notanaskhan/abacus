# S25 support reserve, N lane: live-path fixes, promotions, slot duty, runbooks (Q-04-T090), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081). No pilot firm is live (DEC-1391) and no production stack exists.

Acceptance (as written for the lane): "Every page in the sprint was acknowledged within 15 minutes
and every SEV1/2 has a postmortem within 5 business days." No page and no SEV1/2 in the sprint
(Q-04-T089's record); this record covers the lane's own duties.

## The lane's duties

| Duty | This sprint |
|---|---|
| Live-path defect fixes, through the hotfix lane or the next batch | No live path. The period's defects went through the next batch instead of a hotfix: ED-300 to ED-321, fixed in #1106 and #1111 to #1112 with a recurrence test each (Q-03-T164, T165). No hotfix ran. |
| Weekly production promotion | None: there is no production release (`deploy/production/release.json` holds no digests). |
| In-window slot duty | Rehearsed: the Oct 5 slot and the Oct 11-15 deadline week under the real gate (`docs/ops/windows/`, Q-04-T084, T085). |
| Runbook upkeep | RB-16 §7 gains the window rehearsal step (`abacus_tools.window_rehearsal`) so each window's slots and deadline weeks are checked under the gate before it opens. RB-16 stays `last_rehearsed: never`: the gate rehearsal is one part of it, not the runbook. |

## What only a live firm can show
A live-path defect, its hotfix or batch fix and its time to production; a weekly promotion in a
Tuesday slot with its release record closed by 21:00 CT.
