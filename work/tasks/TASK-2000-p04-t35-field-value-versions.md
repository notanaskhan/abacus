---
id: TASK-2000
title: P-04-T35 Field value versions
spec: SPEC-360
acceptance_criteria: [F8]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T35
branch: s15n-p04-t35
created: 2026-10-29
updated: 2026-10-29
---

## Objective
SHL-09's field routes live behind `review.grammar_api`: the provenance read, a person's edit with a
required citation note (a person's checkpoint where the owner checkpoints), "Add reference"
through C4, field ticks as `field_tick` sign-offs, flags as review notes anchored on the field,
`unsupported` computed, and the `FIELD-001` rule (ADR-160 clauses 5 and 10; P-04 F8).

Acceptance (backlog row): "Halvard interest 2,190 to 2,310 shows the struck prior value, Kevin
Osei's earlier tick reads stale, and an uncited agent value cannot be ticked."

## Plan (red)
- `review/models.py`: map the rest of `field_value_versions` (0093) for reads.
- `review/repository.py`: `field_versions_of`, `field_ticks_of` (LIST-001 exempt: one field).
- `review/field_values.py`: `field_target_id` (uuid5 of target, id, key: the `field` target of a
  tick) and `field_hash` (what a tick signs: the field, its typed value and kind).
- `review/slots.py`: `FieldOwner` gains `label_of`, `apply_edit`, `checkpoints`; new
  `register_field_citations` slot (review never imports evidence).
- `agents/field_citations.py`: registers the slot over `evidence.api` (`supported_citations`,
  `citation_display`, `record_citations`); `evidence.api` exports `citation_display`.
- `review/sign_offs.py`: `tick_field` (live human, `field.sign_off`, independence, unsupported 422
  `uncited_change`, moved hash 409 `content_changed`, R-SO-3 at both levels 409 `segregation`).
- `review/notes.py`: `field_flags` (notes anchored `field` on the key; an access event per body).
- `review/checkpoints.py`: `record_human_edit` (person, `human_edit`, `saved`, in the edit's UoW).
- `review/field_provenance.py`: the service; `field_changed` (409) for a stale `seen_seq`.
- `review/contract.py`: the four routes `_stub` → `_live`; contract stub test LIVE list.
- `banned_patterns`: FIELD-001 (SQL or ORM writes of `field_value_versions` outside
  `review/field_values.py`). Error code `field_changed` (`error_codes --write`).
- No migration, no new matrix row, flag or audit action (`field.value_recorded`,
  `sign_off.recorded`, `checkpoint.saved` exist).
- Rollback: revert the branch; the routes return to 501 behind the flag.

## Acceptance
| Check | Test |
|---|---|
| Halvard 2,190 → 2,310, prior kept, Kevin's tick stale | `test_ac1_halvard_2190_to_2310_struck_prior_and_stale_tick` |
| Uncited agent value: unsupported, no tick | `test_ac2_*` |
| Edit needs a note, reads as the person's, checkpoint, stale seq, preparer only | `test_ac3_*` |
| Ticks are a person's; moved hash; segregation | `test_ac4_*` |
| Flags are notes on the field | `test_ac5_a_flag_is_a_review_note_on_the_field` |
| Unverifiable reference writes nothing | `test_ac6_an_unverifiable_reference_writes_nothing` |
| Flag off and other firms 404 | `test_ac7_flag_off_and_other_firms_are_404` |
| FIELD-001 | `test_ac8_field_001_fails_a_write_outside_record_value` |

All in `backend/tests/integration/backfill/test_p04t35_field_values.py`.

## Progress log
- 2026-10-29: built in one session (S15 build-now block). Tests written first, not yet run: they
  run at the batch's end review (Ayush's rule for this block). ruff, pyright, lint-imports and
  banned_patterns clean. DEC-1050.
