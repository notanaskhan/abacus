# Flag renewal calendar: the P-01 notification flags (P-01-T17)

P-01 §8 and ADR-089: `notifications.v2` and `notifications.email` each carry a calendared renewal or retirement before Mar 1, 2027. Both were created 2026-10-23 and expire 2027-04-21 under the DEC-137 override (`flag-renewals-S4.md`); `make check-fast` fails on an expired flag. Recorded 2026-10-24.

| Flag | Owner | Expires | Due | Action | Condition |
|---|---|---|---|---|---|
| `notifications.v2` | ayushkbhatia | 2027-04-21 | **Thu Feb 25, 2027** | **Retire** | It is on for the Dev, synthetic and canary tenants, which are every tenant until real firms arrive (M9, Jun 1, 2027). Retire it by deleting the flag and the v1 drawer path in one change. If SHL-04's inline approvals or the SHL-04 → SHL-03 link are still deferred on Feb 25, renew it instead to Wed May 26, 2027 (90 days, outside the Jan 1 – Apr 20 freeze) and re-calendar here |
| `notifications.email` | ayushkbhatia | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | It is the per-firm kill switch for notification email (RB-31), so it outlives the rollout. Before it is turned on for any tenant, the `notification.<kind>` email templates are imported for that environment (content, not code). Renew again before May 26 until a platform kill-switch register (P-66) takes it over |

Both dates fall in the S9 renewal train, after the Dec 14–18 bundle and before Mar 1, 2027. A renewal restarts `created` on the day it is made and may reach at most 90 days (ADR-089); record the outcome of each row here.
