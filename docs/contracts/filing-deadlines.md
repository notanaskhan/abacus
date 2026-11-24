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

## Providers registered (T-08-T20, DEC-5917)

Every source kind now has its owner's provider on `platform.register_filing_deadline_source`; practice's recompute asks each registered kind for a window from the season before (400 days) to eighteen months ahead and upserts by `(source_kind, source_ref, filing_label)` on its `inputs_hash`. Practice imports none of the owners.

| Kind | Owner | One fact per | Due · done |
|---|---|---|---|
| `tax_return` | tax | return with a due date (1040 … 706, 990) | extended date when extended, else original; extension form and date whenever known (a 706 without stored dates takes the estate due chip: DOD + 9 months, 4768 + 6, rolled) · filed or accepted |
| `extension` | tax | `filing_extensions` row | the return's original due date · filed or accepted |
| `estimate_batch` | tax | installment due date and form ("Form 1040-ES Q3 · 2026") | the date · every installment paid, scheduled or not required |
| `fiduciary_statement` | tax | Form 706 | Form 8971: 706 due + 30 days · with the 706 |
| `election_window` | tax | Form 1041 | §663(b): 65th day after the year end (the recorded window when one is) · an election recorded |
| `close` | closes | close with a due date ("June 2026 close") | the date · delivered or locked |
| `notice_response` | notices | notice with a respond-by date ("CP2000 response · 2024") | the date · sent, awaiting IRS or closed |
| `form_5500` | assurance | EBP plan audit | last day of the 7th month after the plan year (5558: the 15th of the 10th), rolled past a weekend · report released |
| `assurance_report` | assurance | plan audit with a report target | the target · report released |
| `envelope` | signatures | envelope out for signature (T-08-T18) | due date · completed |
| `consent` | organisations | signed consent whose term ends (T-08-T18) | expiry · superseded by a newer signed one |

Owners are the engagement's preparers and reviewers (a notice: its assignee), the signer its engagement partner. **HOME-01** "Your deadlines" reads these rows (the viewer as owner or signer, open ones, the same walls) once `practice.filing_deadlines` is on, so HOME-01 and HOME-03 show the same dates; `DeadlineRowOut.deadline_id` is additive and `work_item_id` is the deadline's own id when it has no work item.

## DF-10 firm overrides (T-08-T44, DEC-5921)

- **Firm rows** are a firm standard of kind `deadline_overrides` (K-02 lifecycle: created with a partner owner, drafted and published by a person, effective-dated, versioned): `offsets` (`{form, internal_offset_days}`), `closures` (`{date, name}`) and `postponements` (relief notices the firm tracks: `{notice_id, title, areas, window_start, window_end, postponed_to}`). **Platform rows** stay read-only. `GET /v1/standards/deadline-rules` (`firm_standard.read`) is KNW-04 section j: the platform's rules, holidays and notices in effect beside the firm standard (its `allowed_actions` carry draft and publish for its owner) and the overrides in effect.
- **Internal targets**: `filing_deadlines.internal_target_on` for a return whose form has an offset, the statutory (or relief) date less the offset, moved earlier past a weekend, a federal or DC holiday or a firm closure; the detail answers it, HOME-03 keeps the statutory date.
- **Client relief**: `POST /v1/postponement-applications` (`filing_deadline.apply_postponement`, human-only, fresh MFA) takes `notice_id` as the set names it (a string, e.g. `IR-2026-01`; was a uuid in the stub) and the version read (the platform `disaster_postponements` version or the firm overrides version in effect); 409 `postponement_notice_unknown` otherwise. One insert-only row per client and notice (a retry answers the first); only that client's tax rows whose original due date falls in the window move to the notice's date, `postponed_from` keeping the struck original and `postponement_notice_id` the application. `practice.api.due_dates_for(..., tenant_id=, client_id=)` answers the same, with `internal_target_on` and `postponed_from` (additive) and the versions pinned.
