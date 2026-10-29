---
id: TASK-2015
title: N-02-T14 EnvelopeWorkflow v1 on the fake provider
spec: SPEC-381
acceptance_criteria: [AC-6, AC-17]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T14
branch: s15n-n02-t14
created: 2026-10-29
updated: 2026-10-29
---

## Objective
`EnvelopeWorkflow` v1 (`envelope:<tenant>:<envelope>`, time-sensitive): send through the
provider, poll on hints, reminders on the policy's schedule, expiry, and on completion one
evidence package per signer with a manifest in COMPLIANCE storage, the signed copy filed and one
`envelope.completed` (N-02 §3.3, §3.5, §3.7; DEC-1056).

Acceptance (backlog row): "A fake two-signer envelope completes under replay with both packages
hashed in COMPLIANCE storage and one envelope.completed."

## Plan (red)
- `signatures/provider.py`: the provider protocol and its configuration slot.
- `signatures/workflows.py`: the workflow (orchestration only; instants and codes in history).
- `signatures/activities.py`: send, poll, remind, expire, complete (system actor, one unit of
  work each, audited, retry-safe).
- `signatures/reminders.py`: reminder instants (pure) and the template-sender slot.
- `signatures/api.py`: `WORKFLOWS`, `ACTIVITIES`, `SUBSCRIPTIONS`, `start_envelope` and the
  provider and reminder exports.
- `abacus_tools/fakes/esign.py`: the fake provider (synthetic environments only).
- `abacus_tools/workflows/record_envelope.py` + `tests/workflows/test_envelope_replay.py`:
  histories `envelope-v1-{completed,expired}.json`, recorded at the end review.
- No migration, flag or matrix row.
- Rollback: revert the branch; nothing starts the workflow until N-02-T22's send.

## Acceptance
| Check | Test |
|---|---|
| Two signers complete; packages COMPLIANCE; one envelope.completed | `test_ac_a_fake_two_signer_envelope_completes_with_both_packages_in_compliance` |
| Template sender required; cap | `test_a_reminder_needs_a_template_sender_and_stops_at_the_cap` |
| Weekdays at 9:00, before expiry | `test_reminders_fall_on_weekdays_at_nine_in_the_zone_and_before_expiry` |
| Expiry voids at the provider | `test_an_open_envelope_past_its_expiry_is_expired_and_voided` |
| Replay | `tests/workflows/test_envelope_replay.py` |

In `backend/tests/integration/backfill/test_n02t14_envelope_workflow.py` unless named.

## Progress log
- 2026-10-29: built (S15 group B), stacked on N-02-T13 (`hub.seal_ip`). Tests written first,
  not yet run; histories to record at the end review (needs the container stack).
