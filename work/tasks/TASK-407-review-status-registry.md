---
id: TASK-407
title: Review grammar status registry entries and glossary gaps (P-04-T02)
spec: SPEC-047
acceptance_criteria: [AC-5]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T02
branch: p04-t02-status-registry
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"make check-fast regenerates the StrEnums and status.ts with every SHL-09 to SHL-16 status word, and no review identifier lacks a glossary entry."

## Plan
- **Registry** (`docs/product/status-vocabulary.yaml`, protected; decided by the builder under AMENDMENT-solo):
  - new objects `sign_off_slot` (DF-31), `decision_card`, `field_value` (SHL-09), `suggestion` and `proposal` (ADR-161);
  - `checkpoint` gains the stored `saved` code from P-04 section 4, and `current` becomes derived (ADR-160 clause 9);
  - `review_note`, `issue` and `issue_audit_route` are already complete and stay unchanged.
- **Generated:** `make regenerate` rewrites `backend/src/abacus/kernel/_statuses.py` and `packages/ui/src/status.gen.ts`. Never hand-edited.
- **Glossary** (`docs/product/glossary.md`): add the missing rows under "New terms: review". Remove the `proposal` ban from the Fee proposal row and keep that rule in its Meaning cell (rule 3), so the T05 `proposals` tables pass L12 (X-14).
- **Tests first:** `backend/tests/unit/tools/test_review_status_registry.py` checks the stored codes against the P-04 section 4 CHECK lists, that computed words are never stored, the handoff labels and variants, and that the UI registry carries every object.
- **No migration and no flag.** Rollback: revert the commit and run `make regenerate`.

## What changed
- **Registry, stored codes** (they become StrEnums and CHECK lists):
  - `decision_card`: `awaiting_role`, `decided`, `superseded`;
  - `suggestion`: `pending`, `adopted`, `edited`, `dismissed`, `superseded`, `expired`;
  - `proposal`: `pending`, `approved`, `approved_with_edits`, `rejected`, `superseded`;
  - `checkpoint`: `saved` added.
- **Registry, derived codes** (computed, never stored):
  - `sign_off_slot`: `signed`, `stale` (DF-31; staleness is `content_hash` ≠ the target's hash);
  - `field_value`: `updated`, `edited`, `estimate`, `unsupported` (SHL-09);
  - `checkpoint.current`.
- **Labels** come verbatim from blueprint 3.3.1 and the SHL-09 to SHL-16 handoff specs, except the ones listed in the progress log.
- **Acceptance test:** `MaterialityVersionOut.status` comes off `NO_YAML_ENTRY` in `test_f03_status_vocabulary.py`. Its literal `decided` now has a registry home (`decision_card.decided`), so the strict xfail passed and is now a plain assertion. This tightens the test.
- **Glossary:** twelve new rows under "New terms: review":
  - sign-off kinds and levels, field tick, final approval, sign-off slot and staleness;
  - reviewable, field flag, fix instructions and fix runner, checkpoint restore;
  - suggestion decision, proposal decision, Undo as a compensating event, and the effect hold.
- **Glossary ban fix:** `proposal` is no longer in the Fee proposal row's "Don't use" cell. The cell still bans the bare word for the fee concept, and that rule now lives in the Meaning cell.

## Progress log
- 2026-10-22: built. Checks run: `make check-generated`, `banned_patterns`, `validate_docs`, and the status-vocabulary unit and acceptance tests.
- 2026-10-22: these labels are not verbatim from blueprint 3.3.1, addendum 3.2 or DF-31. Each one is taken from a handoff or plan source, or chosen here:
  - `checkpoint.saved` "Saved": the SHL-16 empty state says "Save checkpoint…". Saved checkpoints show no pill (variant null).
  - `suggestion` states:
    - "Suggestion" is the addendum 3.3 tooltip word;
    - "Adopted by {initials}" is from AUD-31;
    - "Edited by {initials} · was {value}" is from C-31 on AUD-31;
    - "Dismissed" is from AUD-37;
    - "Superseded" and "Expired" have no source wording.
  - `proposal.approved_with_edits` "Approved with edits": built from the SHL-10 CTA "Approve with edits".
  - `proposal.superseded` "Superseded": no source wording.
  - `decision_card.awaiting_role` "Waiting on {person}": the SHL-11 b banner. The card shows no pill there.
  - `sign_off_slot.signed` "✓ {initials}": the SHL-09 and SHL-12 chips.
- 2026-10-22: blueprint 3.3.1 makes checkpoint Approved green, but SHL-16 renders it green-tint. The registry keeps green and records the difference in a comment, to be settled at F-05-T12.
- 2026-10-22: one P-04 data model identifier needs watching. `decision_cards.recommendation_suggestion_id` holds the banned word `recommendation`. ADR-160 clause 8 names the column, so the glossary row allows it as a column compound. L12 checks only tables, classes and functions, so the column passes.
- 2026-10-22: rebased onto P-04-T03 (TASK-408, DEC-134). The glossary now names the tables that exist: `reviewable_notes` and `reviewable_note_events`, which are the plan's `review_notes`, and `sign_offs.level` stored as 1 to 5. The `review_note` registry codes match the 0093 CHECK.
- 2026-10-22: the `human_gates.state` codes (`open`, `done`, `voided`) are not in the registry. `human_gates` is a projection that no surface labels, so T16 adds them if the projector needs a CHECK.
