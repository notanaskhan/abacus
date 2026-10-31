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

## The N-01 inbox, files and intake flags (N-01-T29)

N-01 §0, ADR-089: `inbox.firm_intake`, `files.browser`, `portal.intake_upload` and `matching.firm_intake` each carry a calendared renewal or retirement. All four were created 2026-10-27 and expire 2027-04-21 under the DEC-137 override (`communications.yaml`, `evidence.yaml`, `portal.yaml`, `agents.yaml`), so they ride the same S9 renewal bundle as the flags above: one protected bundle, one deploy. The epic's own dates (created Apr 20 – Jun 15, 2027; retired Jul 6 and Aug 10) assumed flags created in 2027; the conditions below keep its order on today's expiries. Recorded 2026-11-01 (DEC-1390).

| Flag | Owner | Expires | Due | Action | Condition |
|---|---|---|---|---|---|
| `inbox.firm_intake` | ayushkbhatia | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | Gates `/v1/inbox*` and the Inbox area's live data. Real firms arrive Jun 1, 2027 (M9), so on May 26 renew again to at most Tue Aug 24, 2027. Retire (delete the flag and its 404 branches in one change, as N-01 §0 planned for the Jul 6 train) once it is on for every live firm |
| `files.browser` | ayushkbhatia | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | Gates `/v1/files*`, the evidence drawer and the CLI-02 Files tab. Same path as `inbox.firm_intake`: renew on May 26 to at most Aug 24; retire once on for every live firm |
| `portal.intake_upload` | ayushkbhatia | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | Gates the portal's intake uploads (POR-03 "Upload something else"). Flipped per firm in the Tue Jul 13, 2027 window, which M10's checklist gates on "delta #1 closed": with penetration tests deferred (DEC-1389) that clause stays open, so no firm flips until a decision books the test or waives the clause. Renew on May 26 to at most Aug 24; retire in a train before Sep 1 once on for every live firm, or renew past the window |
| `matching.firm_intake` | ayushkbhatia | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | The matcher's intake mode per firm (N-01-T26's clearance comes first). Renew on May 26 to Tue Aug 24, then in the Aug 17–24 batch, before Sep 1, to at most Mon Nov 22, 2027, so it never expires inside Sep 1 – Oct 20 (the epic's "renewed in the Tue Aug 3 train to Mon Nov 1", kept in substance) |

A renewal restarts `created` on the day it is made and may reach at most 90 days (ADR-089); record the outcome of each row here.
