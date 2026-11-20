# Deadline week Oct 16-20, 2028 watch, window close and the Oct 24 A-08 flips (Q-04-T230), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081): no pilot firm is live (DEC-1391) and no production stack exists. The week is
in the plan's calendar (autumn 2028), not today's (Fri Nov 20, 2026).

Acceptance: "No release ran Oct 16-20, the window is closed in windows.yaml, and the Oct 24 flips
carry rollback refs."

## No release could run Oct 16-20

The Oct 15 deadline falls on a Sunday, so the week is Mon Oct 16 - Fri Oct 20 (IRC §7503; the
P-29 rule in `deploy/windows.yaml`). The real P-29 gate at 09:00 and 19:05 CT each day, and the
Oct 24 slot, with PF-X1 treated as live from Aug 1, 2028 in memory only:

`python -m abacus_tools.window_rehearsal --firm PF-X1 --live-since 2028-08-01 --at …` (eleven
instants; the file keeps PF-X1 synthetic).

| Instant (CT) | Window | Deadline week | Mini-freeze | Tuesday slot | Flip slot | No window facts | defect_only + rollback | + hotfix |
|---|---|---|---|---|---|---|---|---|
| 2028-10-16T09:00:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | 2028-10-09/2028-10-16 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-16T19:05:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | 2028-10-09/2028-10-16 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-17T09:00:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | - | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-17T19:05:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | - | yes | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-18T09:00:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | - | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-18T19:05:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | - | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-19T09:00:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | - | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-19T19:05:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | - | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-20T09:00:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | - | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-20T19:05:00-05:00 | autumn-2028 | 2028-10-16/2028-10-20 | - | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2028-10-24T19:05:00-05:00 | - | - | - | yes | yes | promotes | promotes | promotes |

Every instant of the week refuses a promotion without a hotfix (`deadline_week_without_hotfix`),
the Tuesday slot of Oct 17 included, and none is a flip slot. Mon Oct 16 is also the last day of
the Oct 9-16 mini-freeze. Tue Oct 24, 19:05 CT is outside every window and is a flip slot.

Releases in the week: none. The S52 batch merge (Fri Nov 20, 2026, today's calendar) is not in
the plan's week and promotes nothing to production; there is no production stack.

## Window closed

`deploy/windows.yaml` records `closed: 2028-10-20` on `autumn-2028`. `release_windows check`
refuses a `closed` date before the window's last day (its end, or the end of a deadline week that
runs past it); the guards read the dates only, so the record changes no gate.
`make windows YEAR=2028` prints "closed Fri Oct 20, 2028".

## The Oct 24 flips (firms live on EBP or tax work)

A-08 §0: five flags flip per firm on Tue Oct 24 in the 19:00 CT slot. `audits.confirmations` waits
for Dec 5 (after the November delta pen test), and `confirmation_links` is a kill switch, not a
flip. Each flip needs an e2e pass, a shadow run, a written rollback and an approver (P-29 rule 3);
the solo builder approves on PF-X1 only (DEC-4822).

| Flip | Flag | Firm | Slot | Rollback ref |
|---|---|---|---|---|
| 1 | `audits.fieldwork_testing` | PF-X1 (synthetic) | Tue Oct 24, 2028, 19:05 CT | `make flag FIRM=PF-X1 FLAG=audits.fieldwork_testing VALUE=off ROLLBACK="A-08 §0 flag-off"`: AUD-12 answers 404 and shows the C-20 not-turned-on state; recorded results do not change |
| 2 | `audits.analytics` | PF-X1 (synthetic) | Tue Oct 24, 2028, 19:05 CT | the same command for `audits.analytics`: AUD-13 and the flux routes answer 404 |
| 3 | `audits.ssars_workspace` | PF-X1 (synthetic) | Tue Oct 24, 2028, 19:05 CT | the same for `audits.ssars_workspace`: the work item opens its existing record page |
| 4 | `sampling.monetary_unit` | PF-X1 (synthetic) | Tue Oct 24, 2028, 19:05 CT | the same for `sampling.monetary_unit`: MUS leaves the method list; drawn samples stay (RB-46 re-perform) |
| 5 | `audits.fieldwork_agents` | PF-X1 (synthetic) | Tue Oct 24, 2028, 19:05 CT | the same for `audits.fieldwork_agents`: the three modes never run, code steps still do |

The five retire in the Thu Nov 16 train (A-08 §0), before their Fri Nov 17, 2028 expiry.

## What only a live firm can show
The canary and SES results during the week, the providers' status pages, a page reaching the
on-call founder, the e2e pass and shadow run on a real firm's tenant, and the second approver
on a real firm.
