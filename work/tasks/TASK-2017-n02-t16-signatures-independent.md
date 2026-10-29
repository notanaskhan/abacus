---
id: TASK-2017
title: N-02-T16 Independent AC tests for N-02-T13 and T14
spec: SPEC-381
acceptance_criteria: [AC-4, AC-5, AC-6, AC-17]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T16
branch: s15n-n02-t16
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Independent acceptance tests (ADR-078) for the hub and drawer (N-02-T13) and EnvelopeWorkflow
(N-02-T14), from N-02 §3.2, §3.3, §3.7 and SPEC-381, not from the builders' tests.

Acceptance (backlog row): "The suite passes and fails if a reminder exceeds the policy cap or a
package lacks the identity result."

## Coverage (paths the builders' suites do not take)
| Check | Test |
|---|---|
| Walled client-only envelope: no row, count, tile; 404 | `test_a_walled_client_only_envelope_is_in_no_row_count_or_tile` |
| Reveal: MFA first; an unrecorded address is refused, not audited | `test_a_reveal_of_an_address_never_recorded_is_refused_not_invented` |
| Void refused on a declined envelope; reason is a code | `test_a_declined_envelope_cannot_be_voided_and_keeps_its_rows` |
| The firm's own cap (1) | `test_a_reminder_never_exceeds_the_firms_own_cap` |
| Saturday send: weekdays at 9:00 local, before expiry | `test_a_saturday_send_reminds_from_monday_at_nine_local_never_on_a_weekend` |
| Five IRS items in every package via the zip; byte-identical; audited | `test_every_package_in_the_evidence_zip_carries_the_five_irs_items` |
| Replay | `tests/workflows/test_envelope_replay.py` (N-02-T14) |

In `backend/tests/integration/backfill/test_n02t16_signatures_independent.py`.

## Progress log
- 2026-10-29: written (S15 group B), stacked on N-02-T14. Not yet run (end review).
