# PW1 and PW2 on PF-X1 (synthetic, DEC-4100)

Rows: A-01-T30, Q-04-T014, T020, T025, T027, T028, T032, T040, T044, T045, T348, T349, T350;
F-09-T127, T131, T138, T144, T145; R-01-T34; Q-03-T112. **Synthetic (PF-X1).**

## Metrics: W4 to W7 (F-09-T131; Q-04-T044)

`make pilot-metrics` wrote nothing before TASK-7101 (finding 1). After the fix:

| Week (Monday) | New snapshots | Rerun |
|---|---|---|
| 2026-09-07 | 0 (nothing to divide by) | — |
| 2026-09-14 | 2 | 0 new (idempotent) |

The W4/W5 read, `python -m abacus_tools.pilots read --firm <PF-X1> --week 2026-09-14`:

| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner | Action |
|---|---|---|---|---|---|---|---|---|
| Brightwater Hale LLP (synthetic) | 2026-09-14 | 3 | W4 Portal activation: invited client contacts who sign in | 0.0% | 1 (0.0%) | amber | AY | Re-invite the client contacts who have not signed in and ask the partner to raise it at the next status call; read again next week. |
| Brightwater Hale LLP (synthetic) | 2026-09-14 | 3 | W5 PBC items delivered through the portal | 45.8% | 1 (45.8%) | amber | AY | Move the open PBC requests onto the published portal binder and chase them through the portal reminders; read again next week. |

- **W6 baseline (F-09-T131):** 14 days on both enrolments (`pilot_enrolments.baseline_days`).
  No W6 was written: no request was both sent and received inside a seeded week.
- **Invitations and activation (Q-04-T044):** the seed's one client invitation was created by
  staff, not sent by a firm person in a wave, and W4 reads 0.0% for one day; ten days of daily
  counts need the clock run forward. Partial.

## Shadow scoring: W2, W7, W8 (Q-03-T112, F-09-T138, F-09-T144)

`make shadow-report FIRM=<PF-X1> AGENT=<agent>` (`shadow_score.v1`, `override_rate.v1`):

| Agent | Runs | Scored | Agreed | Passes |
|---|---|---|---|---|
| evidence.screener | 0 | 0 | 0 | no |
| evidence.matcher | 0 | 0 | 0 | no |
| evidence.upload_reviewer | 0 | 0 | 0 | no |
| decisions.recommender | 0 | 0 | 0 | no |

**The reason for continuing shadow (Q-03-T112):** no agent is cleared for client data
(`client_data: none` on every agent) and the firm cannot opt in until the providers' terms are
registered (finding 2), so no shadow run reaches a decision. **Champion review (F-09-T138):** the
readouts above, all zero. **Shadow exit (F-09-T144):** not confirmed; PF-X1's shadow is extended
in two-week steps, the acceptance's alternative.

## Modes, flips, setup

- **System of record (Q-04-T065, run here):** `make pilot-mode … --mode system_of_record`
  without `--confirmed-by` is refused (`PilotModeRefused`); after `live`, the move with the
  seeded practice leader as confirming person succeeds. Northwind's audit enrolment reads
  `system_of_record` (confirmed_by set); the Feld return stays in shadow, the firm's tool
  authoritative.
- **K-02 flips (Q-04-T045):** `knowledge.firm_standards` and `rules.reference_sets` (default) →
  true for PF-X1 under the flip guard, rollback named. Publishing a standards version (KNW-04 i)
  was not run.
- **AI opt-in (F-09-T127):** the briefing exists (`docs/ops/pilot/ai-optin-briefing.md`); the
  opt-in is refused until the providers' terms are registered (finding 2).
- **Support session (Q-04-T028):** the firm allows support requests (`operations.support_switch`
  pass); requesting, approving and expiring a 2-hour session needs `make dev` and an operator
  session. Not run.
- **Content load (Q-04-T025, R-01-T34):** PF-X1's clients, PBC lists and templates are the
  seed's, through service APIs and the template import (P-11-T13). The acceptance is the firm
  admin through its screens, signed off: that is real-8. The sender domain verifies on the fake
  SES in R-01-T27's tests; real DKIM and MAIL FROM records (Q-04-T032) need SES and DNS.
- **Rollback (A-01-T30):** the shadow flips above were made and can be undone from their
  rollback link; A-01's own pilot rollback runbook was not rehearsed.
- **Desk (Q-04-T014, T020):** the shared inbox and office hours are outside the product; the
  firm's QI contact is the seeded IT / Security seat (no contact in git); the test page needs the
  paging tool (Q-01-T41).
- **Invoices (F-09-T145):** no invoice date: PF-X1 never has a client-facing month. No amount.
- **Flag retirements (Q-04-T348, T349, T350):** wait under DEC-1530 rule 3, unchanged by DEC-4100.
- **M10 flip plan (Q-04-T040):** not compiled in this run.
