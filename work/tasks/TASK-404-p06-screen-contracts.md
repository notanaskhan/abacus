---
id: TASK-404
title: Screen contracts for BND-01, BND-02, SHL-14 and SHL-20 (P-06-T03)
spec: SPEC-307
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: P-06
plan_key: P-06-T03
branch: p06-t03-screen-contracts
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Every artboard letter is built or recorded (SHL-14 c → A-03) and the link-contract test knows
every target." Write the four P-06 screen contracts from the handoff (revision wins): 24 artboards
post-revision, each with persona, clock and data condition (SPEC-307 AC-8: a scenario per artboard
state with a persona and a clock), the parity tier, DV-1…DV-11 where each applies, copy keys
verbatim, and every link as live or planned.

## What changed
- **Contracts** `docs/screens/{BND-01,BND-02,SHL-14,SHL-20}.md` on `_TEMPLATE.md`, modelled on
  `SHL-01.md`. Artboards: BND-01 a–e (5), BND-02 a–g (7, g from R2), SHL-14 a–f (6, f from R2),
  SHL-20 a–f (6) = 24; 23 built, SHL-14 c (Sample-driven bulk) recorded as deferred to A-03.
  Each contract names the building task per artboard (T09, T12, T13, T16, T22, T24), the API rows
  and matrix actions from P-06 §4.3–4.4, status objects from `status-vocabulary.yaml`, copy keys
  for `screens/<ID>/copy.ts` (strings verbatim from spec.md and revision.md; row data stays seed
  data for P-06-T08), links, the acceptance checklists (spec + revision), figures that must foot,
  AVOID lists, deviations, parity and open gaps.
- **Deviations** placed per screen from P-06 §2.4: DV-7 on BND-01; DV-2, 3, 4, 5, 6, 7, 9, 10 on
  BND-02; DV-6, DV-11 on SHL-14; DV-1, 2, 8, 10 on SHL-20.
- **Manifest** `apps/web/src/routes/manifest/shl.ts`: a comment above the SHL-14 entry records
  artboard c as deferred to A-03, not missing (P-06 §5.5). No entry was edited; every link target
  the contracts name (ENG-07, CLI-05, INB-04, FIL-01, TAX-03, POR-03, POR-04, POR-14, SHL-08,
  SHL-17, SHL-21, SHT-01, INB-02, BND-03, TXP-12, AUD-03, CLS-03 and the four screens) was already a
  manifest ID, so `seed-manifest.mjs` had nothing to add.
- **Link-contract test** `apps/web/src/routes/link-contract.test.ts` rule 5: every screen ID in a
  `docs/screens/<ID>.md` Links "To" column is a manifest screen, and every designed link of a
  contracted screen in `handoff-links.json` is named in its contract.

## Decisions taken in the session
- Clock precedence (DEC-15, revision wins): SHL-14 a–e at Mon Sep 14, 2026, 9:41 AM CT (README
  says Thu Sep 24); BND-02 g at 9:31 AM (README says 9:24); SHL-20 b at Sat Sep 26, 10:16 AM
  (README says Mon Sep 14), as P-06 §2.1 already records.
- Parity is Tier C for all 23 (P-06 §5.5; the template's "A/B/D" column gained C); BND-01/02 lock
  at the end of S10, SHL-14 and SHL-20 stay report-only.
- OQ-1 (who may publish a tax binder) is left to P-06-T01's C5 stub, where the matrix row lands;
  BND-02 b records the recommended answer.

## Progress log
- 2026-10-22: contracts written from `sources/handoff/handoff/screens/<ID>*/` (ACCRUED_HANDOFF_DIR
  unset; HANDOFF_VERSION 2026-10-21 pins the same index hash as `handoff-links.json`). Every
  artboard was sourced; none missing. Checks: `vitest run src/routes/link-contract.test.ts` (19
  passed, rule 5 included), prettier and eslint on the two TS files, `validate_docs` (no new
  violations; the 15 reported are pre-existing in TASK-391…400), `banned_patterns`.
