---
id: TASK-425
title: Screen contracts wave 1 for CLI-01, CLI-02, ENG-01, ENG-02 and ENG-03 (P-07-T01)
spec: SPEC-307
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T01
branch: p07-t01-screen-contracts
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Each contract lists every artboard with its production or fixture status and the link-contract
test knows every outbound target." Write the five wave-1 P-07 screen contracts from the handoff
(revision wins): every artboard post-revision with persona, clock and data condition (SPEC-307
AC-8: a scenario per artboard state with a persona and a clock), the parity tier, prod or fixture
status, the DEC-43 deviation for CLI-01c, the DEC-47 header count, the planned-target table, copy
keys and AVOID.

## What changed
- **Contracts** `docs/screens/{CLI-01,CLI-02,ENG-01,ENG-02,ENG-03}.md` on `_TEMPLATE.md`, modelled
  on `BND-01.md`. Artboards: CLI-01 a–f (6), CLI-02 a, a2, b–e and f from R2 (7), ENG-01 a–e (5),
  ENG-02 a–e and f, g from R2 (7, plus the spec'd prospect banner), ENG-03 a–f and g, h from R2
  (8) = 33. All are built in P-07: 26 live in production at the epic's exit, 7 fixture-only until
  the named epic registers the target (CLI-02 d → P-09/P-10, f → I-03; ENG-02 f, g → K-04;
  ENG-03 e → T-01, g → A-09, h → X-01). ENG-02 a's RunCard and close groups are fixture until
  C-01; CLI-02 b's consent row and sync chip until T-01. Each artboard names its building task
  (T12, T19, T20, T21, T27, T28, T34).
- **Manifest** `apps/web/src/routes/manifest/{cli,eng}.ts`: comments above CLI-02, ENG-02 and
  ENG-03 record the fixture-only artboards and where they land (the SHL-14 pattern). No entry was
  edited. Every target the contracts name (CLI-04/05/06/07/08, ENG-04/05/06/07/08/09/10/11/12/13/14,
  BND-02, BND-04, INB-04, INS-05, TAX-02, PRJ-01, TXP-10, TXP-12, HOME-03, FIL-01, AUD-02, AUD-03,
  AUD-07, AUD-15, SIG-01, CLS-02/04/06/09/12/13, NOT-02, SHL-14, SHL-17, SHL-20, WB-11, ATT-05) is
  already a manifest ID, so `seed-manifest.mjs` had nothing to add. CLI-03 is `unindexed` in
  `handoff-links.json` (DEC-32), so CLI-02 records it below its Links table, not in the "To"
  column, and it gets no manifest entry (the manifest holds exactly the handoff's screen IDs).
- **Decision log** DEC-138: P-07 OQ-1 (CLI-01c joins DF-14), OQ-5 (data-derived counts, parity
  mask), OQ-7 (relationship partner stored; manager and preparer derived), and screen IDs inside
  handoff strings are dropped from `copy.ts`.

## Decisions taken in the session
- Viewer precedence (revision wins): ENG-02 b is Priya Raman (spec.md says Margaret Okonkwo;
  README and R2 say Priya), as P-07 §2.1 records.
- CLI-01 a's pane caption reads "{total} clients" ("184 clients", DEC-47) instead of "16 most
  recently active"; c then reads 183 with no wall footer (DEC-43).
- CLI-01 d copy is the handoff's "No clients match 'Schwab'." (P-07 §1 abbreviates it).
- ENG-03 d's banner keeps "Acceptance is not approved yet (G1)." and gains DEC-39's "Start
  acceptance"; "…in CLI-07." and "(ADM-04)" are dropped (DEC-138).
- Production hides CLI-02's dock until P-09; parity for the P0 lock runs on fixture builds.
- Contradictions left for the seed task (recorded under Open gaps): ENG-02 b's "5 of 5 confirmed ·
  Kira Ross pending assignment" vs CLI-08 a's "4 of 5" with Ana Cruz pending at the same clock;
  the interim seed still names the Thornbury client "Estate of Walter Thornbury" (DEC-62); CLI-01
  row 9's last activity names an agent pre-screen v1 does not run.

## Progress log
- 2026-10-23: contracts written from `sources/handoff/handoff/screens/<ID>*/` (HANDOFF_VERSION
  2026-10-21 pins the same index hash as `handoff-links.json`). Every artboard was sourced; none
  missing. Checks: `vitest run src/routes/link-contract.test.ts` (19 passed, rule 5 included),
  prettier and eslint on the two manifest files, `validate_docs`, `banned_patterns`.
