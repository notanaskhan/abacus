---
id: TASK-7100
title: "Every S0–S25 row that needs a pilot firm runs on PF-X1, synthetic (DEC-4100)"
spec: SPEC-403  # go-live check and dossier (Q-04-T009, AC-11; Q-04 AC-6.5)
acceptance_criteria: [AC-11]
risk_zone: amber  # ops tooling; no migration, no matrix, no flag
status: in-review
branch: pfx1-go-live
worktree: /Users/ayushkbhatia/Accrued/abacus-pfx1
created: 2026-11-10
updated: 2026-11-10
---

## Objective
Ayush, 2026-11-10 (DEC-4100): run every S0–S25 row whose acceptance needs a pilot firm on the
synthetic test pilot firm PF-X1 (Brightwater Hale), including the clauses DEC-1530 left open,
each reported as "synthetic (PF-X1)". The list and outcomes: `docs/plan/status/PF-X1-runs.md`.

## Plan (amber)
- Decision: DEC-4100 in `docs/product/decision-log.md`; `accessibility-audit-deferral.md`
  §The test pilot firm rewritten to match.
- `abacus_tools.go_live --rehearse-real`: `tenant.real` passes as "synthetic (<code>): rehearsed
  as real" only for a firm `deploy/windows.yaml` lists as synthetic; the report carries
  `rehearsal: true`. Refused (exit 2) for any other firm; `evaluate` raises for a real one.
- `abacus_tools.go_live_dossier`: `fill` stamps a rehearsal; `check --ready --rehearsal` for a
  `PF-X…` dossier only, needs the rehearsal stamp, accepts `green (synthetic)` by-hand rows and a
  synthetic acknowledgement; plain `--ready` refuses a rehearsal stamp and synthetic rows.
- Tests first: `backend/tests/unit/tools/test_t7100_rehearse_real.py`.
- Runs on the local stack only (worktree offset 30); records in `docs/ops/pilot/pf-x1/`; the PF-X1
  dossier filled from the rehearsal; §Real-firm go-live checks added.
- Seed: synthetic contract pack in `brightwater_hale/files/pf_x1/` (dossier evidence, never
  loaded into the tenant). A `go_live` slice designating the break-glass account through ADM-06's
  service was written and dropped: the service refuses an exempt account without a hardware key
  (`SsoExemptNeedsHardwareKey`), which a seed cannot give a person.
- Rollback: revert the commits; the flags and checks behave as before (rehearsal is opt-in).

## Progress log
- 2026-11-10: decision recorded; 117 search hits read, 86 rows on the list; tooling and tests
  in; local stack seeded (`pilot portal portal_pbc people`), go-live checks at four levels,
  shadow flips, dossier fill, metrics (after TASK-7101), shadow scores, system-of-record move,
  K-02 flips, window rehearsal, flag calendar, fake CCH suites, 54 fixture journey tests run.
  Outcomes: 25 done, 43 partial, 18 blocked. Seven findings for the product in
  `docs/ops/pilot/pf-x1/README.md`.
