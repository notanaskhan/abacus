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

## Q-02's firm export flag (Q-04-T350)

Q-04-T350 retires `compliance.firm_export` in the **Thu Aug 5, 2027** train, before its **Wed Aug 25, 2027** expiry, once on-demand firm export works at every live firm (Q-02 hand-off, Q-02-T51). No live firm exists (DEC-1391), so its retirement condition cannot hold: under that decision's rule 3 the flag is renewed on its calendar instead. Created 2026-10-24, it expires 2027-04-21 under the DEC-137 override (`docs/architecture/feature-flags/evidence.yaml`).

| Flag | Owner | Expires | Due | Action | Condition |
|---|---|---|---|---|---|
| `compliance.firm_export` | notanaskhan | 2027-04-21 | **Thu Feb 25, 2027** | **Renew** to Wed May 26, 2027 | Gates `/v1/firm/data-exports*` (dual approval, DEC-72); off answers 404. It is on for the Dev and synthetic tenants only. Renew again on May 26 to Wed Aug 25, 2027 |
| `compliance.firm_export` | notanaskhan | 2027-08-25 | **Thu Aug 5, 2027** | **Retire** if on-demand export works at every live firm; else **Renew** to at most 90 days | Q-04-T350's acceptance: not registered after the Aug 5 train. With no live firm on Aug 5, renew (DEC-1391 rule 3) and carry the retirement to the first train after the last live firm's export check |

A renewal restarts `created` on the day it is made and may reach at most 90 days (ADR-089); record the outcome of each row here.

## The P-04 review flags (P-04-T62)

P-04 §8, ADR-089. Recorded 2026-11-03 (DEC-2221). The epic named five flags; two never existed.

| Flag | Owner | Was | Now | Action | Condition |
|---|---|---|---|---|---|
| `review.grammar_api` | ayushkbhatia | expires 2027-04-21 | — | **Retired** | Every C3 service it stood in front of has landed (P-04-T16 to T35); it was on for every tenant (Dev, synthetic, canary). Deleted with its 404 branches in `review/contract.py` and `agents/contract.py` and its SHL-10/11/12/15 wrappers in `sheets-host.tsx`, in one change |
| `review.approve_agent_output` | ayushkbhatia | expires 2027-04-29 | expires **2027-05-01** | **Renewed** (DEC-137, 180 days at most) | Per-firm switch for SHL-10's live approval; flipped per pilot firm Tue Jul 13, 2027. Renew again before May 1 (outside the Jan 1 – Apr 20 and Sep 1 – Oct 20 freezes); retire once on for every live firm |
| `review.checkpoints` | ayushkbhatia | expires 2027-04-28 | expires **2027-05-01** | **Renewed** (DEC-137) | Tax-pilot shadow Jul 27, live Aug 17, 2027. Renew before May 1, or retire with the pilot |
| `review.sign_offs` | — | never created | — | **None to retire** | Sign-offs went live behind `review.grammar_api` (P-04-T18); no separate flag was registered |
| `review.issues` | — | never created | — | **None to retire** | DEC-1752 kept SHL-15 behind `review.grammar_api` until a `review.issues` flag; none was registered, so retiring the C3 flag opens SHL-15 with the rest |

The epic's "outside Jan 1 to Apr 20, 2028" assumed flags created in 2027. Today's flags were
created in 2026, so a renewal reaches at most 180 days (DEC-137) and lands before 2028. May 1,
2027 is outside both freeze windows.

## The A-04 planning flags (A-04-T40)

A-04 §8, ADR-089. Recorded 2026-11-03 (DEC-2226). Each expires Apr 28–29, 2027 under DEC-137: none
inside the Jan 1 – Apr 20, 2028 freeze. The rollout is `docs/runbooks/audit-planning-flip.md`.

| Flag | Expires | Action | Condition |
|---|---|---|---|
| `assurance.materiality` | 2027-04-29 | **Renew** to Dec 30, 2027 before expiry | First real-firm flip Tue Oct 26, 2027; retire in the Dec 14 train once on for every live firm |
| `assurance.risk_register` | 2027-04-29 | **Renew** to Dec 30, 2027 | Flip Tue Nov 9; retire Dec 14 |
| `workpapers.core`, `workpapers.drafting` | 2027-04-29 | **Renew** to Dec 30, 2027 | Flip Tue Nov 9; retire Dec 14 |
| `assurance.internal_control` | 2027-04-29 | **Renew** to Dec 30, 2027 | Flip Tue Nov 23 (in the window); retire after the season if AUD-10 stayed dark |
| `ledger.tb_mapping` | 2027-04-28 | **Renew** to Dec 30, 2027 | Flipped Oct 19 (Q-04-T092); retire Dec 14 |
| `home.approvals` | 2027-04-28 | **Renew** to Dec 30, 2027 | Flips Tue Nov 2 and Nov 9 (Q-04-T097, RB-48); retire Dec 14 once on for every live firm |
| `ebp.modules` | 2027-04-30 | **Renew** to Dec 30, 2027 before expiry, then in the M15 bundle (Tue Dec 7, 2027) to after Apr 20, 2028 | First EBP flip after the CPA memo; retire once on for every live firm after PW4 (A-05-T62, `docs/runbooks/ebp-modules.md`) |
| `ebp.form5500_tieout` | 2027-04-30 | **Renew** as `ebp.modules` | Flips last, after AUD-20 on the firm; retire after PW4 |
| `assurance.estimates_rp` | 2027-04-30 | **Renew** as `ebp.modules` | Retire after PW4 |

## The P-09 agent dock and trace flags (P-09-T20, Q-04-T130)

P-09 §8 and ADR-089: `agent_dock.enabled` and `run_trace.enabled` (`agents.yaml`, owner
notanaskhan) were created 2026-11-08 and expire 2027-05-07 under the DEC-137 override, outside the
Jan 1 – Apr 20 freeze. The plan's registry-only renewal ("Tue Feb 15", to "May 12" in the plan's
calendar) maps to today's calendar as the S9-style renewal train before the freeze ends: renewing
now would only move the expiry into the freeze (90 days from Nov 10, 2026 is Feb 8, 2027), so no
YAML changes in S34. Recorded 2026-11-10 (DEC-3212).

| Flag | Owner | Expires | Due | Action | Condition |
|---|---|---|---|---|---|
| `agent_dock.enabled` | notanaskhan | 2027-05-07 | **Thu Apr 22, 2027** | **Renew** to Wed Jul 21, 2027 | Registry-only: the PR changes only `agents.yaml` and carries both founders' approvals. Retire once the dock is on for every live firm (after the canary, then the firm waves); the v1 Agent-tab list is deleted in the same change |
| `run_trace.enabled` | notanaskhan | 2027-05-07 | **Thu Apr 22, 2027** | **Renew** to Wed Jul 21, 2027 | The same PR. Retire with the dock; the drawer's v1 trace path and the step route's 404 branch go together |

Apr 22, 2027 is the first renewal day after the freeze, and Jul 21, 2027 is 90 days on.
