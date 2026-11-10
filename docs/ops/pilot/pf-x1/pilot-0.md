# Pilot 0 on PF-X1 (synthetic, DEC-4100)

Rows: F-09-T32, T33, T51, T56, T61, T69, T70, T72, T73, T74, T77, T82, T84, T86, T89, T93, T95,
T101, T109, T113, T121, T122, T126; F-04-T32, A-01-T27, Q-01-T55, Q-03-T084. **Synthetic
(PF-X1).** No real firm signed an LOI (DEC-1391); PF-X1 is the only Pilot 0 partner.

## M3: LOIs and the fallback (F-09-T32, T33)

- **LOIs:** 0 signed. The M3 fallback is recorded by DEC-4100: Pilot 0 runs on synthetic data,
  on PF-X1. The anonymised-list replay and PW1 on Jun 15 are not re-planned here (Ayush).
- **Google Workspace check:** PF-X1 runs no Google Workspace: its staff sign in through the local
  fake OIDC server and its mail goes to the platform sink. So no CASA application follows from
  PF-X1. The CASA go/no-go itself is a company decision and stays Ayush's (DEC-2098).

## Discovery, plan and sandbox (F-09-T51, T56, Q-01-T55)

- Discovery notes: [`docs/product/discovery/pf-x1-discovery.md`](../../../product/discovery/pf-x1-discovery.md).
- **Plan:** six sessions, waves A to F, each walked on PF-X1 on 2026-11-10 (below); the firm's
  PBC template is Northwind's seeded PY2025 list (AUD-03's 24 rows, `portal_pbc` slice).
- **Sandbox:** PF-X1 is the sandbox; its tenant is `synthetic = true`. The three *staging*
  provisions of Q-01-T55 are staging-only: `make seed-staging RESET_CLOCK=E0` (the ECS one-off
  task, after the deploy lock) plus two TenantProvisioningWorkflow runs with `synthetic = true`.

## Sessions A to F, as journey walks (F-09-T61, T69, T77, T84, T89, T95, T101; F-04-T32)

A Pilot 0 session on the synthetic firm is a walk of the session's journeys on its seed, the
fixture project (`ABACUS_FIXTURES=1 pnpm exec playwright test --project=fixture …`, worktree
offset 30). One run, 2026-11-10: **40 passed, 14 skipped, 0 failed** (3.8 min).

| Wave | Row | Journeys walked | Result |
|---|---|---|---|
| dry run | F-09-T61 | J02 | passed (fixture). The staging walk: `pnpm -C apps/web exec playwright test --project=staging e2e/journeys/J02-client-onboarding.spec.ts` (Ayush, staging) |
| A | F-09-T69 | J02-audit-core, J12-core | passed |
| B | F-09-T77 | J02, J12 retests | passed; the legacy request-list import of a partner template was not run (needs `make dev`: ImportRequestList on PF-X1) |
| C | F-09-T84 | J04-PBC slice | passed (fixture); full stack (portal upload, scan, screening) needs `make dev` + `make e2e` |
| D | F-09-T89 | J04-PBC on the firm's PBC list (Northwind's AUD-03) | passed (fixture) |
| E | F-09-T95 | A02 TB connections, J23 audit-partner morning (cockpit) | passed |
| F | F-09-T101 | KNW-01 catalog | passed; the workbook re-import through KNW-01 was not run |
| F-04-T32 | | J04-PBC | passed in fixture mode; staging walk and the Sep 24 snapshot load are staging-only |

## Usability log and top ten (F-09-T70, T93, Q-03-T084, A-01-T27)

The walks are automated: no person used a screen, so they found no S1 or S2 finding, and
`python -m abacus_tools.quality.pilot_log` passes on an empty log. The top-10 list v1 is empty;
A-01 owns none of it; Q-03-T084 has nothing to close. Real usability findings need a firm's
people at the screen (real-11 in `docs/ops/go-live/PF-X1.md`).

## Checkpoints and agreements (F-09-T73, T74, T82, T86, T121, T126)

- **M5 note (F-09-T73):** PF-X1 attended every session (synthetic); its champion is the seeded
  practice leader. RK-02 is not met by the test firm. **RK-01 is met in fact:** no real firm has
  signed an LOI; the wedge review is Ayush's.
- **Champion (F-09-T74):** named (the practice leader seat). The draft founding-partner agreement
  is counsel's text and is not written synthetically (DEC-2098).
- **Founding price (F-09-T82):** not run. A synthetic firm's reaction to a price is no signal, and
  the price is Ayush's (DEC-2098).
- **Round 2 (F-09-T86):** counsel's redlines; not synthetic.
- **Exit (F-09-T121):** top-10 closed (empty); the ledger choice (fake QBO and NetSuite for
  PF-X1) recorded; the letter, consent and DocuSeal templates are loaded through the import API
  (P-11-T13) but their approval by counsel is not synthetic.
- **Retro and metrics (F-09-T126):** the retro is this file; the PW1 success metrics are W4 to
  W7 as computed (`pw1-pw2.md`), signed off by the synthetic champion. W4 to W8 are still not in
  `thresholds.md` (F-09-T62).

## Tax sessions (F-09-T72, T109, T113)

- **CCH admin:** the seeded Tax Manager seat (New York) acts as PF-X1's CCH admin; the seed holds
  224 tax-return work items, and the Feld 2025 return is enrolled. The 5 to 15 extended 1065 and
  1040 returns are not listed one by one.
- **Session 1:** the fake CCH Axcess import of a synthetic export file and its difference log:
  `tests/unit/fakes/test_t01t22_cch_axcess.py`, `tests/unit/tax/test_t01t26_engine_files.py`,
  `test_t01t44_independent.py`: **30 passed**; no difference logged.
- **Session 2:** no format difference to close; the K-1 release walkthrough was not walked.

## PW1 engagements (F-09-T122)

PF-X1's shadow engagements: the Feld 2025 return (`tax_return`) and Northwind's PY2025 EBP audit
(`assurance`), enrolled 2026-09-01 to 2027-10-20, baseline 14 days. PHI check: the scenario's
data is generated; no PHI-bearing engagement type is enabled for synthetic data.
