# Tax pilot and the autumn window on PF-X1 (synthetic, DEC-4100)

Rows: T-01-T22, T-01-T28, P-04-T47, T-02-T34; F-09-T142, T146, T151, T152, T154, T156, T158,
T166, T176, T178, T184; Q-04-T061, T064, T065, T072, T077, T079; Q-03-T151; the AY-lane support
reserves Q-04-T037, T042, T047, T052, T060, T069, T075, T082. **Synthetic (PF-X1).**

## Tax pilot

- **Fake CCH (T-01-T22):** the adapter suite passes against the fake and the scenario's sample
  files (30 passed with T-01-T26 and T-01-T44's suites); the fake refuses a non-synthetic
  tenant. The "partner-validated" files are validated by the synthetic firm's CCH admin seat.
- **PWT enablement (T-01-T28):** the consent templates are counsel's (not synthetic); CCH
  integration rows, mappings and the T-01 flags in shadow for PF-X1 were not set in this run.
- **j06 coordination (P-04-T47):** staging-only: `pnpm -C apps/web exec playwright test
  --project=staging e2e/journeys/J06-1040-season.spec.ts` after `make seed-staging`. J06 passed
  in fixture mode here.
- **W10 (F-09-T166):** cannot be read: `pilot_metrics` computes W4 to W7 only; W10 has no source.
- **Runbooks (T-02-T34):** not rehearsed here (staging); approval of the flip plans is the
  founders'.
- **KBA (F-09-T158):** DocuSeal production KBA is on Accrued's account (Ayush).

## Window rehearsal (Q-04-T077, F-09-T178, F-09-T184)

`python -m abacus_tools.window_rehearsal --firm PF-X1 --live-since 2027-08-02 --at …` (PF-X1
treated as live in memory only, DEC-2081):

| Instant (CT) | Window | Deadline week | Mini-freeze | Tuesday slot | Flip slot | No window facts | defect_only + rollback | + hotfix |
|---|---|---|---|---|---|---|---|---|
| 2027-09-21T19:05:00-05:00 | autumn-2027 | - | - | yes | yes | refused: window_mode_missing, rollback_missing | promotes | promotes |
| 2027-09-14T10:00:00-05:00 | autumn-2027 | 2027-09-13/2027-09-17 | 2027-09-08/2027-09-15 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |
| 2027-09-28T10:00:00-05:00 | autumn-2027 | 2027-09-27/2027-10-01 | 2027-09-23/2027-09-30 | no | no | refused: window_mode_missing, rollback_missing, deadline_week_without_hotfix | refused: deadline_week_without_hotfix | promotes |

- **Sep 21 Tuesday slot (Q-04-T077):** the slot and flip slot are open; a defect-only release with
  a rollback promotes. The flip still needs the audit CPA's sampler memo (a real person's),
  staging green within 24 h and both approvals: open.
- **Deadline weeks (F-09-T178, T184):** inside Sep 13–17 and Sep 27–Oct 1 a defect-only release
  without a hotfix is refused, so no partner request becomes a live-path change. No partner
  request was made.

## Flags across the window (Q-04-T061)

`make flag-calendar` and the season check: no flag expires between Sep 1 and Oct 20, 2027
(`season.flags_outside_window` pass on PF-X1, rehearsed as real).

## Window notice, system of record (Q-04-T064, T065)

- **Notice (Q-04-T064):** acknowledged for PF-X1 by its synthetic champion and admin seats, on
  the RB-16 partner-facing text. Synthetic.
- **System of record (Q-04-T065):** Northwind's audit moved to `system_of_record`, confirmed by
  the seeded practice leader; refused without a confirming person (`pw1-pw2.md`).

## Desks and reserves (Q-04-T072, T079; Q-04-T037 to T082)

No request reached a desk: PF-X1 has no live channel, so no champion contact, no KBA fallback
case and no support hour was logged; RK-07 is not raised. The real desk is real-10.

## Not synthetic (counsel, prices, reports)

F-09-T142 (counsel-approved FAQ), T146, T152 and T156 (season-2 agreements and their counsel
rounds), T154 (a reference: a synthetic firm's reference is no reference), T176 (no Type II
report exists), Q-03-T151 (no agent at live stage, so no sample to label). F-09-T151's retro for
PF-X1 records its season-2 intent: stay the rehearsal firm.
