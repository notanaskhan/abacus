# Deadline week Oct 11-15, 2027 watch (Q-04-T085), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081): no pilot firm is live (DEC-1391) and no production stack exists. The week is
in the plan's calendar (autumn 2027), not today's.

Acceptance: "No release or flip ran in the week and every daily check is logged."

## No release or flip could run

The real P-29 gate at 09:00 and 19:05 CT each day, with PF-X1 treated as live in memory only
(`abacus_tools.window_rehearsal`; rehearsal records with zero digests):

| Instant (CT) | Window | Deadline week | Mini-freeze | Tuesday slot | Flip slot | No window facts | defect_only + rollback | + hotfix |
|---|---|---|---|---|---|---|---|---|
| 2027-10-11T09:00:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-11T19:05:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-12T09:00:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-12T19:05:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | yes | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-13T09:00:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-13T19:05:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-14T09:00:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-14T19:05:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-15T09:00:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-10-15T19:05:00-05:00 | autumn-2027 | 2027-10-11/2027-10-15 | 2027-10-08/2027-10-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |

Every day of the week refuses a promotion without a hotfix (`deadline_week_without_hotfix`), the
Tuesday slot included, and no instant is a flip slot. The week sits inside the Oct 8-15
mini-freeze. A hotfix would promote, and RB-16 then wants both founders' approval in its incident
record: the gate does not hold that approval, the incident record does.

## Daily checks (RB-16 §6, deadline weeks)

| Day | Canary | SES deliverability | Providers' status pages | Primary and backup reachable | Flips | Releases |
|---|---|---|---|---|---|---|
| Mon Oct 11 | not run: no production canary yet | not run: SES sending is not live (Q-01-T47 staging sink only) | not run: no provider in production use | rota: N primary, AY backup, double cover (`docs/ops/on-call.md`) | none (0 planned in `make flag-calendar`) | none: every promotion refused without a hotfix |
| Tue Oct 12 | not run: no production canary yet | not run: SES sending is not live (Q-01-T47 staging sink only) | not run: no provider in production use | rota: N primary, AY backup, double cover (`docs/ops/on-call.md`) | none (0 planned in `make flag-calendar`) | none: every promotion refused without a hotfix |
| Wed Oct 13 | not run: no production canary yet | not run: SES sending is not live (Q-01-T47 staging sink only) | not run: no provider in production use | rota: N primary, AY backup, double cover (`docs/ops/on-call.md`) | none (0 planned in `make flag-calendar`) | none: every promotion refused without a hotfix |
| Thu Oct 14 | not run: no production canary yet | not run: SES sending is not live (Q-01-T47 staging sink only) | not run: no provider in production use | rota: N primary, AY backup, double cover (`docs/ops/on-call.md`) | none (0 planned in `make flag-calendar`) | none: every promotion refused without a hotfix |
| Fri Oct 15 | not run: no production canary yet | not run: SES sending is not live (Q-01-T47 staging sink only) | not run: no provider in production use | rota: N primary, AY backup, double cover (`docs/ops/on-call.md`) | none (0 planned in `make flag-calendar`) | none: every promotion refused without a hotfix |

The rota check (`python -m abacus_tools.quality.on_call`) passes: every day of Oct 11-15 has a
primary and a different named backup on double cover. The other three checks need production and
are logged as not run, not as clean.

## What only a live firm can show
The canary and SES results, the providers' status during the week, a page that reaches both
founders, and the partner desk's extended hours (Q-04-T086).
