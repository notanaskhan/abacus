# Q-04-T110: the Dec 14-17 bundle, recorded at the S30 build (2026-11-08)

Row: renewals to expiries after Apr 20, 2028 (A-05, T-01, P-04); A-06 flags retired into
`assurance_completion`; N-04 and T-03 flags retired; `make flag-calendar` shows no expiry inside
Jan 1 to Apr 20.

| Clause | State | Where |
|---|---|---|
| A-06 flags into `assurance_completion` | built | A-06-T37 (#1435, migration 0713, DEC-2714): `assurance.completion` and `adjustments.entries` removed; the module entitlement gates AUD-15/16/17/20 and the adjustments routes |
| N-04 flags retired | done in S29 | N-04-T27 (#1384): `notices.workspace`, `notices.responder` |
| T-03 flags retired | done in S29 | T-03-T18 (#1387): `tax.extensions_estimates`, `questionnaires.editor` into the `tax_returns` entitlement |
| Renewals past Apr 20, 2028 (A-05, T-01, P-04) | cannot be written yet | a renewal runs at most 180 days from its own day (DEC-137); a Dec 14, 2027 renewal reaches Jun 11, 2028. Every flag now expires Apr 21 to May 1, 2027, so each is renewed in turn; the Dec 14-17, 2027 renewal is the last before the window. P-11's three are listed in RB-68 §6 |
| `make flag-calendar` | passes today | 78 flags, none expiring inside a release window, none within 21 days. The 2028 check is the Dec 14-17, 2027 run |

Flag calendar at main + the S30 stack (`python -m abacus_tools.codegen.feature_flags --calendar`):
52 flags expire 2027-04-21, 1 on 04-26, 7 on 04-27, 4 on 04-28, 6 on 04-29, 3 on 04-30, 5 on
05-01. All are after the 2027 window (Jan 1 to Apr 20) closes; the first renewal train is the week
of Apr 15, 2027.

**Partial (ops, dated):** the renewals themselves and the Dec 14-17, 2027 calendar run. Nothing in
code is left for this row.
