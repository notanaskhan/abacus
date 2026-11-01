---
updated: 2026-11-01
---
# On-call rotas (Q-04-T020, Q-04-T066; Q-01-T41; `docs/ops/pilot/README.md`)

Who takes a page, per live window. Severity is ADR-097's. This file names founders by handle and
firms by pilot code only: no phone numbers, no email addresses, no firm or person names (the
contacts live in the vault and in the paging tool). `python -m abacus_tools.quality.on_call`
(check-fast) refuses a window day without a primary and a different named backup, and a
deadline week of a release window (`deploy/windows.yaml`) that is not on double cover.

## Rules
- **SEV1 pages both** founders at once, 24x7, in and out of quiet hours (README: acknowledged within
  15 minutes; status page within 30).
- **SEV2** pages the primary; unacknowledged after **15 minutes** it escalates to the backup.
  Outside a live window's working hours (Mon–Fri, 8:00 AM–6:00 PM CT) a SEV2 is acknowledged by the
  next business morning.
- **SEV3** never pages: it is filed on the owning epic within one business day (AY).
- **Quiet hours** (in writing, per the agreement): 9:00 PM–7:00 AM CT every day, and weekends.
  Inside them only SEV1 pages, on `single` cover.
- **Double cover** (Q-04-T066; every day of a deadline week, and only those): SEV2 pages the
  primary and the backup together, with no 15-minute wait; quiet hours are suspended, so SEV2
  pages at any hour, weekends included; SEV1 is unchanged (both, at once). A rota row is either
  wholly in a deadline week or wholly outside one.
- **Swaps** are a PR to this file before the day, both founders approving; `updated:` moves with it.

## Windows

| Window | Starts | Ends | Live firms (pilot codes) |
|---|---|---|---|
| PW1 | 2027-06-01 | 2027-07-12 | PF-A1 |
| autumn-2027 | 2027-09-01 | 2027-10-20 | |

A rota window named after a `deploy/windows.yaml` window keeps that window's dates (through its
last deadline week, DEC-806) and its deadline weeks. `autumn-2027` has no live firm: no pilot firm
is signed (DEC-1391), and PF-X1, the synthetic test firm (DEC-1530), is never live, so the rota is
published for the window and rehearsed against PF-X1.

## Rota

| Window | From | To | Primary (SEV1/2) | Backup | Cover | Notes |
|---|---|---|---|---|---|---|
| PW1 | 2027-06-01 | 2027-06-06 | N | AY | single | go-live week (M9, Tue Jun 1) |
| PW1 | 2027-06-07 | 2027-06-13 | N | AY | single |  |
| PW1 | 2027-06-14 | 2027-06-20 | N | AY | single |  |
| PW1 | 2027-06-21 | 2027-06-27 | N | AY | single | pen-test delta #1 runs from Jun 21 |
| PW1 | 2027-06-28 | 2027-07-04 | N | AY | single |  |
| PW1 | 2027-07-05 | 2027-07-12 | N | AY | single | M10 prep (Tue Jul 13) |
| autumn-2027 | 2027-09-01 | 2027-09-12 | N | AY | single | window opens; mini-freeze from Sep 8 |
| autumn-2027 | 2027-09-13 | 2027-09-17 | N | AY | double | deadline week (Sep 15) |
| autumn-2027 | 2027-09-18 | 2027-09-26 | N | AY | single | mini-freeze from Sep 23 |
| autumn-2027 | 2027-09-27 | 2027-10-01 | N | AY | double | deadline week (Sep 30) |
| autumn-2027 | 2027-10-02 | 2027-10-10 | N | AY | single | mini-freeze from Oct 8 |
| autumn-2027 | 2027-10-11 | 2027-10-15 | N | AY | double | deadline week (Oct 15) |
| autumn-2027 | 2027-10-16 | 2027-10-20 | N | AY | single | window closes Oct 20 |

## Firm incident contacts (each firm's QI contact)

The contact itself is in the vault entry named here, never in git. RB-27 uses it when an Accrued
incident touched the firm.

| Pilot code | Contact | Vault entry | Recorded |
|---|---|---|---|
| PF-A1 | the firm's QI partner | — | not yet: no PW1 firm is signed (F-09) |

## Test pages

Acceptance (Q-04-T020): a test page reaches N and escalates to AY after 15 minutes. Send a
SEV2-routed test alert from the paging tool, do not acknowledge it as N, and record when each
founder was reached. Acceptance (Q-04-T066): on a double-cover day the same alert reaches N and AY
together, at any hour; send one inside quiet hours during the first deadline week's rehearsal.

| Date | Sent | N reached | Escalated to AY | Minutes to escalate | Result |
|---|---|---|---|---|---|
| — | — | — | — | — | not run: the paging tool (Q-01-T41, Better Stack) is not provisioned |
| — | — | — | — | — | double cover not run: same reason (Q-04-T066) |
