---
id: TASK-1701
title: F-06-T02 tax-season specimen fixtures at E0
spec: SPEC-400
acceptance_criteria: [AC-34]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T02
branch: s14-f06-t02
created: 2026-10-27
updated: 2026-10-28
---

## Objective
Typed TS seed modules for the tax specimens at E0 (Mon Sep 14, 2026, 9:24 AM CT): the TY2025 practice
board, envelopes E1–E10 with E6 in full, Ridgeline's capital rollforward and memo, the T10 letters
and email, the Feld binder at 390, the personas mira-kapoor and dina-sato, footing tests and the L10
scan over the new files.

## Plan
- `apps/web/src/fixtures/seed/tax/`: `tax-returns.ts` (224 rows; the roster mirrors the Python
  `binders.build_returns`, statuses from TPL-01 a/b, §9.7 R1–R30 and §9.3, the rest by stable rank
  so §9.5 foots), `envelopes.ts`, `ridgeline.ts`, `letters.ts` (T10/TPL-10 canvases, verbatim),
  `feld-mobile.ts` (derived from `binder-detail.ts` via a new `FELD_REQUEST_FACTS`), `index.ts`.
- Figures are whole-dollar decimal strings; `__tests__/tax.foot.test.ts` sums them in BigInt.
- Personas in `apps/web/e2e/harness/personas.ts`.
- L10: `seed_contamination.py` also scans `apps/web/src/gallery/specimens/` (the fixtures root
  already covers `seed/tax/`).

## Per AC
| AC | Tests |
|---|---|
| AC-34 | `tax.foot.test.ts` (17): 224 / 79 / 145; every status count; 161 extended; offices 98 / 64 / 62; Awaiting signature = E1–E10; 2,296 and 410; masked TINs; rollforward crossfoots and foots both ways; 6,866,200; 331,405; tie-out; 1,256,200; 733,500; state shares; Feld 2 → 1 to do |

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Lakeshore's 990 keeps its original Nov 16, 2026 due (no Ext. tag); one more done return is on extension, so 161 still foots (78 open + 83 done) | §9.3 gives the original date with 8868 available, §9.5 says all 79 open are extended: the sources disagree on one row | no |
| A named return's office is the board's (TPL-01, §9.7), and the office quota counts it | the TPL-01 rows win for the specimen; offices still read 98 / 64 / 62 | no |
| Unnamed returns' preparer, reviewer and sync day are drawn by stable rank from the office's tax seats | no source names them | no |

## Progress log
- `2026-10-28` — Modules, personas, scan root and footing tests built. Targeted run: `vitest run src/fixtures/seed/__tests__/tax.foot.test.ts` 17 passed; eslint and tsc clean on the touched files. Full gates at batch end.

## Handoff
- **Current state:** built, PR open (stacked on F-06-T01), held for the S14 batch.
- **Exact next step:** batch-end `make check-fast` (seed_contamination over the new root).
