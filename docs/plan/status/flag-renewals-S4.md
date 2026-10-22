# Flag renewals for the Dec 14–18 bundle (S4)

Nine flags expire between 2027-01-05 and 2027-01-13, inside the busy-season freeze; `make check-fast` fails on an expired flag. Renew or remove each in the Dec 14–18, 2026 bundle (DEC-68). Recorded in SU-16 (F-01-T01 part 2), 2026-10-20.

| Flag | Expires | Owner | Action |
|---|---|---|---|
| `prompt.evidence.screener` | 2027-01-05 | ayushkbhatia | renew or remove |
| `engagement_agent.enabled` | 2027-01-07 | ayushkbhatia | renew or remove |
| `retrieval.auto` | 2027-01-07 | ayushkbhatia | renew or remove |
| `ledger.import` | 2027-01-08 | ayushkbhatia | renew or remove |
| `upload_review.enabled` | 2027-01-09 | ayushkbhatia | renew or remove |
| `uploads.processing` | 2027-01-09 | ayushkbhatia | renew or remove |
| `ledger.gl_import` | 2027-01-12 | ayushkbhatia | renew or remove |
| `matching.enabled` | 2027-01-12 | ayushkbhatia | renew or remove |
| `guidance.drafting` | 2027-01-13 | ayushkbhatia | renew or remove |
| `fieldwork.assessor` | 2027-01-17 | ayushkbhatia | renew or remove |
| `fieldwork.procedures` | 2027-01-17 | ayushkbhatia | renew or remove |
| `engagements.work_items_api` | 2027-01-20 | ayushkbhatia | re-date or retire (F-03-T37); retire once P-07 wires ENG-01/02 |
| `notifications.v2` | 2027-01-20 | ayushkbhatia | renew (P-01 wire-up, P-01-T17 calendars it) |
| `notifications.email` | 2027-01-20 | ayushkbhatia | renew (P-01-T12) |
| `review.grammar_api` | 2027-01-20 | ayushkbhatia | renew (C3 live routes, retired S26) |
| `binders.engine` | 2027-01-20 | notanaskhan | renew (C5 live in S6) |

## Why this waits for Dec 14–18 (checked 2026-10-23, S4 batch)

F-03-T37's acceptance is "no flag expiring before Feb 1, 2027 and no flag owned by 'founder'".
- **Founder-owned flags:** there are none. Every flag names a person.
- **Expiry:** a flag's expiry must fall within 90 days of its `created` date (ADR-089; the generator refuses anything later). A renewal therefore restarts `created` on the day it is made. Renewing on 2026-10-23 can reach 2027-01-21 at the latest, which fails the Feb 1 bar.
- **When:** the renewal runs in the Dec 14–18 bundle as planned, and F-03-T37 stays open until then. A renewal made on Dec 14 can reach Mar 14, 2027.
- **Freeze rule:** the plan's flag rule says no expiry inside Jan 1 – Apr 20 for flags that live firms use. On Dec 14, each renewal should choose either an expiry after Apr 20 (by renewing again in late January) or retirement. Record the choice per flag here.
