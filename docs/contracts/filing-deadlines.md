# Filing deadlines v1 (FD-1) — calendar, rule detail, exports and relief

| Field | Value |
|---|---|
| Owner | practice (T-08; SPEC-710); answers F-07-T21's request |
| Status | stub (T-08-T04, 2026-11-18; DEC-5603); v1 S53 |
| Code | `backend/src/abacus/modules/practice/filing_deadlines_contract.py` (`filing_deadlines_router`) |
| Flag | `practice.filing_deadlines` (default off; off: 404; on: 501 until T-08-T10/T21/T44) |
| Consumers | HOME-03, HOME-01 pane (I-01), I-02 Today, I-04 HOME-04, R-03 |

Rows are metadata only, never TRI or amounts. Every portal principal 403 (AC-18) → flag 404 → human-only 403 → 501. Risk tiers (`overdue`, `due_7`, `due_30`, `later`, `done`) and days left are computed on read in the firm's zone and never stored.

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/filing-deadlines?from=&to=&view=month\|week\|list&office_id=&service=&person_id=&risk=` | `filing_deadline.read` | items, day counts ("+n more"), holidays; walls contribute nothing |
| `GET /v1/filing-deadlines/{id}` | `filing_deadline.read` | rule popover: rule text and reference-set versions from the row (C21) |
| `GET /v1/filing-deadlines/export?format=xlsx\|ics&from=&to=` | `export.create` | one-off, fresh MFA; no TIN or amount; no feed |
| `POST /v1/postponement-applications` | `filing_deadline.apply_postponement` | DF-10 client relief, human-only, fresh MFA |

**Provider protocol (T-08-T07):** `platform.register_filing_deadline_source(kind, provider)`, `provider(ctx, window) -> list[FilingDeadlineFact]`; an unregistered `source_kind` fails at startup. Recompute upserts by `(tenant_id, source_kind, source_ref, filing_label)`, idempotent on `inputs_hash`.

**Examples:** Sep 15, 2026 holds 12 = 8 × 1065 + 3 × 1120-S + 1; Thornbury 706 Nov 2, 2026 (4768 → May 3, 2027); TY2028 1040 Tue Apr 17, 2029.
