---
id: TASK-2014
title: N-02-T13 Firm envelope read models and actions live
spec: SPEC-381
acceptance_criteria: [AC-4, AC-5, AC-6]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T13
branch: s15n-n02-t13
created: 2026-10-29
updated: 2026-10-29
---

## Objective
SIG-01's routes live behind `signatures.envelopes`: the list with wall-safe counts and tiles,
the summary, the drawer with `allowed_actions`, the 10-second IP reveal, the evidence zip and
void with a reason (N-02 §3.2, §3.3; DEC-1055).

Acceptance (backlog row): "Grace Holloway's Out for signature tab returns 17 rows with tiles 8,
5, 4 and 4, and a walled engagement's envelope is absent with no count."

## Plan (red)
- `signatures/hub.py`: the read model and the three actions over Core table clauses (no ORM
  models for 0292's tables yet). Visibility per DEC-33; `allowed_actions` per status.
- `signatures/contract.py`: six routes from `_stub` to live; the other C7 routes stay stubs.
- `evidence/records.py` + `evidence/api.py`: `get_record` (digest-verified read-back).
- `evidence/signed_copies.py` + `evidence/api.py`: `version_titles` for the drawer's documents.
- C7 stub test: the six routes join LIVE.
- OpenAPI and client regenerated (descriptions and error lists only; no shape change).
- No migration, flag, matrix row or audit-target change.
- Rollback: revert the branch; the routes return to 501 behind the flag.

## Not built here
- Provider-side void (W7, N-02-T18): a `fake` or `docusign` envelope is voided locally only.
- Evidence integrity alarm and "Evidence integrity check failed" (N-02-T38).
- `note` on declined rows and the work item's long label ("TY2025 Form 1040 · Thomas & Irene
  Kowal →"): the row carries the work item's name; SIG-01 composes the rest.

## Acceptance
| Check | Test |
|---|---|
| 17 rows, tiles 8/5/4/4, walled row absent, summary foots | `test_ac_graces_out_tab_returns_17_rows_with_tiles_and_no_walled_row` |
| Tabs, search and paging under `visible()` | `test_tabs_and_search_stay_under_visible` |
| Drawer masks the address; walled 404 | `test_the_drawer_masks_the_address_and_hides_walled_envelopes` |
| Reveal: reason, MFA, no-store, audited | `test_a_reveal_needs_a_reason_and_mfa_and_is_audited` |
| Void: reason, evidence kept, closed 409 | `test_a_void_needs_a_reason_keeps_evidence_and_closes_the_envelope` |
| Evidence zip audited and byte-identical | `test_the_evidence_zip_is_audited_and_byte_identical` |
| Flag off | `test_the_flag_off_answers_404` |

All in `backend/tests/integration/backfill/test_n02t13_envelope_hub.py`.

## Progress log
- 2026-10-29: built (S15 group B). Tests written first, not yet run (end review).
