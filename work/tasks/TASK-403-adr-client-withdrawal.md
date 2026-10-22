---
id: TASK-403
title: "P-06-T28 · ADR P-31 Client withdrawal of unaccepted uploads (ADR-162), detached-key crypto-erase"
spec: SPEC-046
acceptance_criteria: [AC-5, AC-6, AC-17]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T28
branch: p06-t28-adr-withdrawal
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"ADR-137 is Accepted with both founders as deciders before T01 merges, and it records the erase mechanism, the 30-day window and that accepted evidence is never withdrawable." Drafted from chapter 09 (P-31), DEC-58 (b) and epic P-06 section 4.2's erase mechanism (OQ-5).

## Plan (red zone; documents only)
- Number: the plan alias ADR-137 is the module map on `main`, so take the next free number, ADR-160 and ADR-161 having just been minted by TASK-402: ADR-162. Record the mapping in `docs/adr/backlog.md` (AC-5).
- Files: `docs/adr/ADR-162-client-withdrawal-unaccepted-uploads.md`; index row in `docs/adr/README.md` (AC-6); `docs/adr/backlog.md` row P-31; decision-log artefact for DEC-58 (AC-17).
- No migration, registry, flag, test or product code. Rollback: revert the commit.
- Check: `cd backend && uv run python -m abacus_tools.quality.validate_docs`.

## What changed
- **ADR-162 (P-31, accepted):** the one enumerated exception to ADR-004/034; **accepted evidence is never withdrawable** (ever-accepted, including an undone acceptance, answers `409 evidence_accepted`); who may withdraw (`client_admin` in scope, `client_contributor` own uploads; firm, agent, system, support deny); withdraw voids and hides from firm reads, agents and exports at once, with request status rollback; **erase mechanism: detached-key crypto-erase** (envelope ABE2, `evidence_object_keys`, retained on acceptance, SECURITY DEFINER erase by the purge role; ciphertext ages out under GOVERNANCE), chosen over rolling retention, early override delete and hide-only; **30-day window** on `kernel.clock`; purge skips while held and fails closed without a hold check; derived records erased with the key.
- `docs/adr/README.md`: index row. `docs/adr/backlog.md`: P-31 = ADR-162, accepted. `docs/product/decision-log.md`: DEC-58 -> ADR-162.

## Progress log
- 2026-10-22: Read P-06 epic (sections 0, 3.7, 4.2, 4.4, 7, 11; OQ-5), chapter 09 (P-31, DEC-58, DF-15), ADR-004, ADR-033, ADR-034, ADR-104, RB-13, and `evidence/storage.py` and `kernel/crypto` for the current ABE1 content-addressed layout. Drafted and accepted ADR-162 with deciders notanaskhan and ayushkbhatia (solo-edition reading). Index, backlog and decision log updated. validate_docs passes for these files.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| ADR-162 for P-31, not the plan's ADR-137 | ADR-137 is the module map on `main`; backlog.md treats plan numbers as aliases | No (recorded in backlog.md) |
| Erase mechanism: detached-key crypto-erase (OQ-5) | The epic's recommended option; erases on day 30 without break-glass | Recorded in ADR-162 |
| A client admin may withdraw contributors' unaccepted uploads in scope (OQ-5) | The epic's proposed answer; audited | Recorded in ADR-162 |
| "Accepted" means ever accepted, including an undone acceptance | Acceptance stamps the key retained and retention is one-way, so an erase could never complete | Recorded in ADR-162 |
| Previews under the version's data key; extraction results and search projections deleted by the purge | They are derived and rebuildable (ADR-110); the erase must cover every copy of the content | Recorded in ADR-162 |
| Pre-detached-key client uploads are not withdrawable; no backfill | Only synthetic tenants hold them before the M7 gate | Recorded in ADR-162 |
