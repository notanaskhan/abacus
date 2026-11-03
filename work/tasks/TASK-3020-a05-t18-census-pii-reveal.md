---
id: TASK-3020
title: A-05-T18 census PII sealing and field reveal
spec: SPEC-641
acceptance_criteria: [AC-F2]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T18
branch: s25-a05-t18 (stacked on s25-a05-t20)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"A participant's SSN and date of birth are sealed on import and shown only through a logged,
MFA-fresh, onshore person's reveal; an agent, a client principal or an offshore member is refused
and nothing opens."

## Plan (red)
- Migration 0652 (on 0651, expand only): `pii_reveals.field_ref`; a reveal names a region and its
  evidence version (P-03, unchanged) or a field (`pii_reveals_region_or_field`). Rollback: the
  downgrade is refused once a field reveal exists (the table is insert-only).
- `evidence/reveals.reveal_field`: P-03's rules for a sealed field the owner opens only after the
  reveal is recorded (person only, `pii.reveal` with fresh MFA, shared 20 an hour, `pii.revealed`
  audited without the value). Exported through `evidence.api`.
- `assurance/ebp_participants.py`: `seal_pii` (AAD `ebp_participant:<import>:<key>:<field>`,
  fingerprints under the firm's key, last four), masks, `reveal`.
- Route `POST /ebp/participants/{id}/reveals` served: `ParticipantRevealOut` (value restricted),
  `no-store`, gate on `ebp.read` then the flag; `pii.reveal` is authorised by the reveal.
- Tests: `tests/unit/assurance/test_a05t18_participant_pii.py`,
  `tests/integration/trust_kit/test_a05t18_participant_reveal.py`.

## Progress log
- 2026-11-02: built. Unit tests pass; the integration file runs in the end pass. The census
  import (A-05-T19) calls `seal_pii`; until it lands no row carries a sealed value. Client
  regeneration runs in the end pass (`make regenerate`).

## Decisions made during this task
DEC-2067.
