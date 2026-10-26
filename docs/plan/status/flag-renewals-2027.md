# Flag renewal calendar: the P-01 notification flags (P-01-T17)

P-01 §8 and ADR-089: `notifications.v2` and `notifications.email` each carry a calendared renewal or retirement before Mar 1, 2027. Both were created 2026-10-23 and expire 2027-04-21 under the DEC-137 override (`flag-renewals-S4.md`); `make check-fast` fails on an expired flag. Recorded 2026-10-24.

| Flag | Owner | Expires | Due | Action | Condition |
|---|---|---|---|---|---|
| `notifications.v2` | ayushkbhatia | 2027-04-21 | **Thu Feb 25, 2027** | **Retire** | It is on for the Dev, synthetic and canary tenants, which are every tenant until real firms arrive (M9, Jun 1, 2027). Retire it by deleting the flag and the v1 drawer path in one change. If SHL-04's inline approvals or the SHL-04 → SHL-03 link are still deferred on Feb 25, renew it instead to Wed May 26, 2027 (90 days, outside the Jan 1 – Apr 20 freeze) and re-calendar here |
| `notifications.email` | ayushkbhatia | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | It is the per-firm kill switch for notification email (RB-31), so it outlives the rollout. Before it is turned on for any tenant, the `notification.<kind>` email templates are imported for that environment (content, not code). Renew again before May 26 until a platform kill-switch register (P-66) takes it over |

Both dates fall in the S9 renewal train, after the Dec 14–18 bundle and before Mar 1, 2027. A renewal restarts `created` on the day it is made and may reach at most 90 days (ADR-089); record the outcome of each row here.

## The P-06 requests and binders flags (P-06-T27)

P-06 §0 and §4.9, ADR-089: `binders.engine`, `screening.card` and `evidence.withdrawal` each carry a calendared renewal or retirement. All three expire 2027-04-21 under the DEC-137 override (`docs/architecture/feature-flags/requests.yaml`, `agents.yaml`, `evidence.yaml`). Each is due in the same S9 renewal train as the P-01 flags, so one protected bundle renews five flags and one deploy carries them. A renewal on Thu Feb 25, 2027 reaches Wed May 26, 2027 at most (90 days, no override), and May 26 is outside both freeze windows (Sep 1 – Oct 20 and Jan 1 – Apr 20). Recorded 2026-10-26 (DEC-409).

| Flag | Owner | Expires | Due | Action | Condition |
|---|---|---|---|---|---|
| `binders.engine` | notanaskhan | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | P-06 §0 retires it once MVP-1 is code-complete. On Feb 25 the follow-up override route still answers 501 and the OQ-1 preparer path is not built (SPEC-319 §20), so renew. At the next renewal (by May 26), retire it by deleting the flag and its 404 branches in one change if both are closed; otherwise renew again to at most Tue Aug 24, 2027 and re-calendar here |
| `screening.card` | notanaskhan | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | It gates the SHL-20 routes, whose card shows model-derived findings to firm reviewers; it stays a per-firm switch until A-01's AUD-03 hosts the card and real firms arrive (Jun 1, 2027). Renew again before May 26 if either is still open; retire only with the A-01 host live |
| `evidence.withdrawal` | notanaskhan | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | It must be on before PW2 (Tue Jul 13, 2027). Renew again before May 26 (to at most Tue Aug 24, 2027, past PW2); retire after PW2 once it is on for every firm. Off only stops new withdrawals: a purge already started keeps running (RB-32) |

A renewal restarts `created` on the day it is made and may reach at most 90 days (ADR-089); record the outcome of each row here.
