# November 2028 test readiness (Q-03-T363)

The readiness gate for the Nov 13–24, 2028 window (the W1 delta and the annual test #3, one
call-off: [`../pentests/2028-11-annual-3-scope-addendum.md`](../pentests/2028-11-annual-3-scope-addendum.md)).
Acceptance: "Both founders sign the readiness checklist." Under the solo amendment the builder
signs (`docs/plan/AMENDMENT-solo.md`). **Deferred engagement (DEC-1389):** no window is booked, so
the DAST run against a live target and the signature stay human; everything a session can build is
below.

This file holds results only: never client data, exploit detail, addresses, vendor names, test
credentials or the external ID (the repository is public).

- **Prepared:** Mon Nov 23, 2026, on the S53 stack (TASK-8948). The pinned SHA is the S53 batch
  merge's tip; every `re-run` item is re-run on it in the end pass and its state written here.
- **Companions:** the threat model's delta #4 rows (WP-, PC-, CL-, TH-; `docs/architecture/ai-threat-model.md`).

## Checklist

States: `ready`, `re-run` (built; green on the pinned SHA is the end pass's) or `human`.

| # | Item | Evidence | State | Owner |
|---|---|---|---|---|
| NR-01 | Build pinned | The S53 batch merge tip, CI green on it (one run on the tip, `[skip ci]` on the others) | re-run | session |
| NR-02 | Security files green: tenancy, matrix, route introspection, RLS schema | `backend/tests/security/` (generated over `TABLE_OWNERS` and the matrix) | re-run | session |
| NR-03 | Posting security files green | `backend/tests/unit/adjustments/test_c02t18_posting.py`, `test_c02t19_write_evidence.py`, `test_c02t24_posting_recovery.py`, `backend/tests/integration/backfill/test_c02t36_w1_ac.py` | re-run | session |
| NR-04 | Console and TIN files green | `backend/tests/integration/test_g04t14_console_bff.py`, `backend/tests/integration/backfill/test_c02t57_console_tin_ac.py`, `backend/tests/unit/quality/test_c02t57_connector_read_only.py` | re-run | session |
| NR-05 | Confirmation-link files green | `backend/tests/unit/assurance/test_a08t16_confirmations.py`, `test_a08t18_confirmation_lifecycle.py`, `backend/tests/integration/test_a08t16_confirmations.py` | re-run | session |
| NR-06 | Personas for posting, console and confirmation links | Defined below on PF-X1 (synthetic); accounts are provisioned on staging at booking, never in git | ready (definitions) | session, human |
| NR-07 | DAST baseline with no high alert against the pinned staging build | needs a live staging target and a booked window | human (DEC-1389) | human |
| NR-08 | Threat model current for every November surface | Delta #4 rows WP-01 to TH-04, two gaps listed | ready (N's review open) | human |
| NR-09 | Readiness signed | — | human | human |

## Personas (PF-X1, synthetic; roles only)

| Persona | Firm role / engagement role | Surface it exercises | Must be refused |
|---|---|---|---|
| P-POST-PREP | senior on a CAS engagement with a QBO connection | dry run and post of an approved batch | posting without the client's grant; a second post on the same key |
| P-POST-STAFF | staff on the same engagement | reads the console | post, retry, undo |
| P-POST-CLIENT | client admin of the CAS client | grants and revokes write consent (POR-16) | reading the posting log; another entity's grant |
| P-CONSOLE | platform console staff | console metadata reads | any firm content, a TIN, a write |
| P-CONSOLE-WALLED | firm member walled from one client | the ledger console of another client | the walled client's console, its counts, its TIN reveal |
| P-CONFIRM-RESP | external respondent with one confirmation link | answering its own request once | replay, another request, an expired link |
| P-CONFIRM-MGR | audit manager sending confirmations | creating and voiding links | reading a respondent's other links |
