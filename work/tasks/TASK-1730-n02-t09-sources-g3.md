---
id: TASK-1730
title: N-02-T09 Envelope source registry and G3
spec: N-02 §3.12, §8.2; docs/contracts/c7-envelopes.md
acceptance_criteria: [N-02-T09]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T09
branch: s14-n02-t09
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The fail-closed envelope source slot, the `engagement_letter` source, the signatures G3 provider
replacing P-07's interim one, and the C7 record-mode freeze. Acceptance (backlog row): "By Fri
May 14, 2027 C7 record mode is frozen and Bluestem stays Accepted until a G3 source is met."

## Plan (red)
- `signatures/sources.py`: `EnvelopeSource`, `register_envelope_source`, `envelope_source`
  (fail closed), the letter source, `letter_gate`; registered at `signatures.api` import.
- `signatures/api.py`: `envelope_summary_for`, `envelope_gate_facts` live.
- `engagements/slots.py`: `replace_gate_provider` (G3 only, once); `gates.recorded_letter`
  exported. Error code `unknown_envelope_source`. Contract status: record mode frozen. DEC-820.
- Rollback: revert (P-07's provider returns).

## Acceptance
| Check | Test |
|---|---|
| Bluestem stays Accepted until a G3 source is met | `backend/tests/integration/backfill/test_n02t09_letter_gate.py::test_ac_bluestem_stays_accepted_until_a_g3_source_is_met` |
| Record mode frozen with the letter source | `…::test_ac_c7_record_mode_is_frozen_with_the_letter_source_registered` |
| The G3 truth table over its three sources; the slot fails closed | six tests |

## Progress log
- `2026-10-28` — Built. ruff, pyright, lint-imports clean; error codes written. Tests written,
  not run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch, stacked on #592.
- **Next:** N-01-T09.
