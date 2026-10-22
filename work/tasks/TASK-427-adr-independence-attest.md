---
id: TASK-427
title: ADR-164 Independence and attest-client rules (P-13; P-07-T66)
spec: SPEC-025
acceptance_criteria: [AC-5, AC-7]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T66
branch: p07-t66-adr-independence
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"ADR-142 is Accepted with notanaskhan and ayushkbhatia as deciders before T24 starts, and it
records the derived attest flag, G2 on sign-offs and client-facing actions, the SKE designee and
NAS evaluation for attest clients." Draft proposal P-13 from chapter 09 P-13, DEC-69 and DEC-39,
consistent with DEC-128 (the derived `is_attest_client`, built in F-03-T25) and the identity
independence code of SPEC-025 (TASK-045's `register_independence` slot, AC-5 confirmations and
AC-7 refusals), which this ADR re-scopes for P-07-T24.

## Plan (red zone: written before the ADR)
- Files: `docs/adr/ADR-164-independence-attest-client-rules.md` (new); `docs/adr/README.md` index
  row; `docs/adr/backlog.md` P-13 row and the minted-numbers line; DEC-69's artefact column in
  `docs/product/decision-log.md`.
- No code, migration, matrix, registry or flag edit: P-07-T24 (authz) and P-07-T41 (records)
  implement it. Rollback: revert the commit; nothing depends on it at run time.
- Checks: `validate_docs`, `banned_patterns`, the link-contract test.

## What changed
- **ADR-164** (accepted 2026-10-23, deciders notanaskhan, ayushkbhatia): (1) the attest flag
  stays derived by the `engagements` trigger over the `gate_policy` attest family and live
  statuses (DEC-128), client-level across engagements; (2) G2 v2 on attest-client engagements:
  pending members may view, but `work_item.assign` answers `409 gate_unmet` G2, sign-off answers
  `409 independence_pending` (ADR-160 R-SO-5) through `engagements.api.independence_cleared`, and
  `message.send`, `request_item.send` and `client_access.grant` keep `independence: required`;
  non-attest engagements are not gated; (3) `g2_blocks_view` is stricter only and TASK-045's rule
  stands until T24 merges; (4) one check through the existing `register_independence` slot, fail
  closed, with the DEC-91 annual confirmation joining when G-01 lands; (5) the G2 gate is the EP's
  insert-only conclusion with preconditions; (6) SKE designee required for attest clients
  (DEC-63); (7) NAS evaluation per nonattest service, prepared by a partner or manager, decided by
  the EP (DEC-64); (8) no GL posting for attest clients (P-16 declares `attest_client: deny`);
  (9) no policy principal for attest clients; (10) humans only.
- **Numbering:** the plan's "ADR-142" is the AWS topology (P-55), so P-13 takes the next free
  number, ADR-164; the mapping is recorded in `backlog.md` as for ADR-160…163.
- **Housekeeping:** TASK-425 (P-07-T01) is renumbered TASK-426, because another session's
  F-05-T35 file merged as TASK-425 a minute later.

## Decisions taken in the session
- `nas.evaluate`: P-07 §4.3 gives it to partner and manager, DEC-64 reserves the NAS decision to
  the EP. Read together: a partner or manager prepares a row, the EP decides it.
- Readiness is in DEC-128's attest family, so a readiness engagement makes its client attest;
  when it is the client's only attest-family engagement there is nothing to evaluate it against,
  so no NAS row is required for it. DEC-69's NAS rule then applies to readiness alongside another
  attest engagement.
- Non-attest engagements still request and record per-person confirmation on assignment (DEC-91),
  but it gates nothing there.

## Progress log
- 2026-10-23: ADR drafted and accepted; backlog, README and DEC-69 updated. Checks:
  `validate_docs`, `banned_patterns`, `vitest run src/routes/link-contract.test.ts`.
