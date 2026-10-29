---
updated: 2026-10-30
---
# On-call rotas (Q-04-T020; Q-01-T41; `docs/ops/pilot/README.md`)

Who takes a page, per live window. Severity is ADR-097's. This file names founders by handle and
firms by pilot code only: no phone numbers, no email addresses, no firm or person names (the
contacts live in the vault and in the paging tool). `python -m abacus_tools.quality.on_call`
(check-fast) refuses a window day without a primary and a different named backup.

## Rules
- **SEV1 pages both** founders at once, 24x7, in and out of quiet hours (README: acknowledged within
  15 minutes; status page within 30).
- **SEV2** pages the primary; unacknowledged after **15 minutes** it escalates to the backup.
  Outside a live window's working hours (Mon–Fri, 8:00 AM–6:00 PM CT) a SEV2 is acknowledged by the
  next business morning.
- **SEV3** never pages: it is filed on the owning epic within one business day (AY).
- **Quiet hours** (in writing, per the agreement): 9:00 PM–7:00 AM CT every day, and weekends.
  Inside them only SEV1 pages. In a deadline week (`deploy/windows.yaml`) quiet hours are
  suspended (Q-04-T066 writes that rota for the autumn window).
- **Swaps** are a PR to this file before the day, both founders approving; `updated:` moves with it.

## Windows

| Window | Starts | Ends | Live firms (pilot codes) |
|---|---|---|---|
| PW1 | 2027-06-01 | 2027-07-12 | PF-A1 |

## Rota

| Window | From | To | Primary (SEV1/2) | Backup | Notes |
|---|---|---|---|---|---|
| PW1 | 2027-06-01 | 2027-06-06 | N | AY | go-live week (M9, Tue Jun 1) |
| PW1 | 2027-06-07 | 2027-06-13 | N | AY | |
| PW1 | 2027-06-14 | 2027-06-20 | N | AY | |
| PW1 | 2027-06-21 | 2027-06-27 | N | AY | pen-test delta #1 runs from Jun 21 |
| PW1 | 2027-06-28 | 2027-07-04 | N | AY | |
| PW1 | 2027-07-05 | 2027-07-12 | N | AY | M10 prep (Tue Jul 13) |

## Firm incident contacts (each firm's QI contact)

The contact itself is in the vault entry named here, never in git. RB-27 uses it when an Accrued
incident touched the firm.

| Pilot code | Contact | Vault entry | Recorded |
|---|---|---|---|
| PF-A1 | the firm's QI partner | — | not yet: no PW1 firm is signed (F-09) |

## Test pages

Acceptance: a test page reaches N and escalates to AY after 15 minutes. Send a SEV2-routed test
alert from the paging tool, do not acknowledge it as N, and record when each founder was reached.

| Date | Sent | N reached | Escalated to AY | Minutes to escalate | Result |
|---|---|---|---|---|---|
| — | — | — | — | — | not run: the paging tool (Q-01-T41, Better Stack) is not provisioned |
