# S50 dark trains: Q-04-T352 (Tue Sep 19, 2028) and the T-08 Thu Sep 21 bundle, recorded at the S50 build (2026-11-18)

Rows: Q-04-T352 — Q-05's `quality.management`, `audit.consultations_log`, `audit.post_issuance`
and `records.governance` flags created in the Tue Sep 19, 2028 train, default off, no firm flipped
inside the Sep 1 – Oct 20, 2028 window, and every later Q-05 flag event recorded. The same record
covers T-08's six flags (T-08-T03, the Thu Sep 21 train after Q-05-T02's bundle, one protected
bundle per train).

| Clause | State | Where |
|---|---|---|
| Four Q-05 flags exist, default off | done | `docs/architecture/feature-flags/{practice,assurance,evidence}.yaml` (Q-05-T02, #2287, DEC-5609); `_flags.py` regenerated |
| Six T-08 flags exist, default off | done | `docs/architecture/feature-flags/{engagements,practice,tax}.yaml` (T-08-T03, #2280, DEC-5602) |
| Expiry outside a window | done | created 2026-11-18, expires 2027-05-17 (the DEC-137 180-day override); no release window binds a synthetic firm (DEC-68) |
| One protected bundle per train | done | Q-05-T02 first, T-08-T03 second, each its own PR; both merge in the S50 batch in that order |
| No firm flipped inside the window | holds | no flag event is written by code; PF-X1 stays off (DEC-4100) |
| Later Q-05 flag events recorded | ops | each flip is a person's, recorded in `docs/ops/pilot/pf-x1/season.md` when it happens (Q-04-T353, Q-04-T354) |

**Partial (ops, dated):** the Sep 19 and Sep 21, 2028 trains themselves are calendar events; nothing
in code is left for this row.
