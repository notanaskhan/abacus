---
id: TASK-393
title: Scenario-level golden-figure tests (F-04-T12)
spec: SPEC-307
acceptance_criteria: [AC-6]
risk_zone: amber
status: done
epic: F-04
plan_key: F-04-T12
branch: f04-t12-scenario-goldens
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"YAML goldens with sources assert counts and Northwind and Granite Peak figures by exact Decimal
equality" (F-04.27; ADR-078; ch. 03 §10.3).

## Plan
Tests only. No migration, flag, registry or product-code edit. Expected values are transcribed from
F-04 §3.2/§3.6 and blueprint 01 §9.1, §9.4, §9.5, §9.7 and §9.8, never from the code (ADR-078).
Rollback: revert the commit.

## What changed
- `backend/tests/golden/scenario/brightwater_hale/{practice_counts,audits,northwind,granite_peak}.yaml`:
  each case has `inputs`, `expected`, `source` and `reviewed_by`. Materiality and lost-earnings
  cases also carry a `parameter_set`. `reviewed_by` reads `pending (AY)` until a review memo exists.
- `backend/tests/golden/scenario/test_brightwater_hale_golden.py`:
  - the loader is a `SafeLoader` subclass with the int and float resolvers removed, so every number
    is source text and goes to `Decimal`;
  - one parametrised test per case;
  - one scenario test per case that has a `scenario` probe;
  - Hypothesis footing properties: sums are order-free and split; materiality rounds to 100 and
    PM/CT are exact parts of the rounded overall; any subset of the 27 audits foots by type and by
    stage.
- `tests/golden` is collected by default (`testpaths = ["tests"]`). Hypothesis was already a dev
  dependency.

### Checked against the scenario package
- `clients-184`: 16 + 66 + 102, read from `build().clients` by origin.
- `seats-46-named-and-generator`: 14 + 32.
- `seats-46-by-office`: 22 + 14 + 10.
- `offices-3`: 1 HQ + 2 branches.
- `holdout-fairhaven-183` and `holdout-copperleaf-183`: `build(holdouts=...)`.
- `audits-27-roster-rows`: each §9.7 row resolves to exactly one scenario client by name or by a
  plan entity (A1 → Northwind, A14 → Granite Peak), with the row's EP as `partner`. `attest` is
  true for the EBP, FS audit and Review rows and false for the AR-C 70/80 rows (27/27/27). The
  tallies by type and stage are arithmetic over the rows, because engagements arrive with F-04-T13.

### Arithmetic only (inputs → expected; read back from the loaded state by F-04-T29)
- `audits-27-by-type` (14 + 6 + 4 + 3) and `audits-27-by-stage` (7 + 9 + 6 + 2 + 3).
- `northwind-pbc-11-of-24`.
- `granite-peak-fs-pbc-41` (38 received + 3 overdue, ENG-12).
- Northwind:
  - net assets 16,812,400 + 48,600 = 16,861,000, also by line (16,500,000 + 312,400 + 48,600);
  - investments 14,895,000 + 1,605,000;
  - comparative 13,940,000 + 288,500 = 14,228,500;
  - net increase 2,583,900;
  - receivable 33,540 + 15,060;
  - loan rollforward 288,500 + 96,200 − 57,450 − 14,850 = 312,400 and loan count 41 + 5 − 7 − 3 = 36;
  - materiality 1.0% = 168,100, and 1.5% = 252,200 with PM 189,150 and CT 12,610;
  - VFCP lost earnings 33,540.00 × [(1 + 0.07/365)^10 − 1] = 64.38.
- Granite Peak: gross profit, pre-tax income 3,100,000, and materiality 155,000 / 116,250 / 7,750.

The materiality rounding rule is written down in A-04 AC3.1 and blueprint §9.4: the overall
figure is rounded to the nearest 100, half up, and PM 75% and CT 5% are taken from the rounded
overall. CT is 5% of overall materiality, not of PM.

### Source conflicts
None between the scenario package and the spec or blueprint, so no case is xfail.
One note inside the plan: ch. 05 WB-02 reads "PBC 12 of 24", while F-04.10, blueprint §9.7 A1
and §9.4 read 11 of 24. DF-34 already settles it at 11, and the golden keeps 11.

`banned_patterns` requires an issue reference (`#nnn`) on any xfail. A future conflict therefore
needs AY's issue number before its case can be marked
`xfail(strict=True, reason="source conflict: ... #nnn")`.

## Progress log
- 2026-10-22: built under the S3 batch rules. `pytest tests/golden/scenario` gives 38 passed.
  ruff format, ruff check, pyright (strict) and `banned_patterns` are clean on these files.
  Full suites were not run.
- 2026-10-26 (S10 code gap, branch `s10-f04-t29-goldens`, F-04-T29): `tests/integration/test_f04t29_loaded_goldens.py` reads the goldens back from a loaded E0: 184 clients by name with their primary entities, 46 staff seats by office, 3 offices, the 27 audit roster rows (entity, type group, phase, EP), and each holdout loading 183. Strict xfail citing this task: the loader writes no client facts (kind, office, relationship partner, attest, portal status) and only each client's primary entity (Thornbury's estate entity is missing at E0). northwind.yaml and granite_peak.yaml stay arithmetic until their engines load the figures.
- 2026-10-27 (S10, branch `s10-task393-client-facts`): the loader writes each client's record facts through `set_client_record` (kind mapped to the record's vocabulary: individual/household → household, business/partnership → business, exempt_org → nonprofit, trust/estate → trust_family, plan → plan_sponsor; office; relationship partner; portal status) and every further entity except the plan entities the audits add. Attest stays derived (DEC-128). F-04-T29's strict xfail came off: 5 passed. The acceptance slice no longer adds Thornbury's estate entity (audit_core does). Scenario, binders, portal and fixture-equivalence suites: 146 passed, 6 xfailed (pre-existing).
