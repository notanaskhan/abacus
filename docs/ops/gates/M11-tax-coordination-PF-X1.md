# PF-X1 · M11 go-live evidence pack (T-01-T47)

The tax pilot's coordination layer goes live for the test pilot firm **PF-X1** (Brightwater Hale,
synthetic; DEC-1530). Everything here is synthetic evidence and is reported as PF-X1's, never as a
live firm's. Founder decision 2026-11-01 (DEC-1680): the go-live proceeds without pen-test delta #2
(deferred, DEC-1389), and without the gates that need a live firm or a hosted journey runner; each
is listed below as waived, not as met.

## 1. The flip

Four T-01 flags on for PF-X1 (`293fc3e7-be13-4767-ae6a-ce245b2dbda9`), one ops-task run each on
**staging** (Actions › ops-task › Run workflow; production only by an ops-request PR). PF-X1 is a
pilot firm in `deploy/windows.yaml`, so the flip guard refuses a run without an approver who is not
the operator and a rollback link. Synthetic, so no window or slot applies.

| Flag | ops-task command | args (JSON) |
|---|---|---|
| `consents.registry` | `abacus_tools.flags` | `["--firm","293fc3e7-be13-4767-ae6a-ce245b2dbda9","--flag","consents.registry","--value","true","--operator","<you>","--reason","T-01-T47 M11 go-live (PF-X1, synthetic)","--approved-by","<other founder>","--rollback","docs/ops/gates/M11-tax-coordination-PF-X1.md#3-rollback"]` |
| `clients.tax_profile` | `abacus_tools.flags` | the same, `--flag clients.tax_profile` |
| `tax.engine_bridge` | `abacus_tools.flags` | the same, `--flag tax.engine_bridge` |
| `tax.delivery_efile` | `abacus_tools.flags` | the same, `--flag tax.delivery_efile` (M13's flag; on with M11 for the test firm only) |

Then `abacus_tools.go_live` with `["--firm","293fc3e7-be13-4767-ae6a-ce245b2dbda9","--level","tax"]`
and paste its JSON under §4.

## 2. Evidence

| Item | Result | Where |
|---|---|---|
| C19 consumer suites | 42 passed on main c22b0ea42 (2026-11-01) | `backend/tests/contracts/c19` |
| I-7216 and I-OFFSHORE | 10 passed (the offshore fixture now swaps the real registration and restores it) | `backend/tests/security/test_tri_and_offshore.py` |
| Never-ERO and transmitter | 22 passed | `backend/tests/security/test_never_ero_transmitter.py` |
| Classification scrubbing (no TRI, TIN, bank number or engine message in logs, Sentry or metrics) | 51 passed | `backend/tests/security/test_classification_scrubbing.py` |
| Journey specs | fixture project green (J06, J07, J08, J12, J13 incl. j06 D/relock and the T-02/N-02 steps; 42 passed, S21 batch 4 end review); **on staging: waived** (the staging journey job is off until `ABACUS_STAGING_URL` is set, F-04-T28) | `apps/web/e2e/journeys` |
| Shadow reconciling to CCH | **synthetic only**: PF-X1's Feld 2025 return in shadow against the fake CCH (`--slice pilot`); a real firm's CCH reconciliation is on DEC-1530's still-needs-a-real-firm list | `make shadow-report`, `docs/ops/go-live/PF-X1.md` |
| Pen-test delta #2 closed | **waived** (DEC-1389 deferred it; DEC-1680 proceeds without it) | `docs/plan/status/pen-test-deferral.md` |
| Written rollback | §3 | this file |
| Both founders' approval | Ayush: DEC-1680 (2026-11-01). The other founder: the `--approved-by` on each flip | the `feature_flag.set` audit events |
| No T-01 flag expires between Sep 1 and Oct 20, 2027 | holds: all four expire 2027-04-27; the Aug 24-26 bundle renews them past Oct 20 (Q-04-T061) | `docs/architecture/feature-flags/{organisations,tax}.yaml` |

## 3. Rollback

Any time, without the slot: the same command with `--value false` for each flag, `--hotfix "<why>"`
and the other founder approving. Turning the flags off hides the routes (404) and TAX-09's actions;
nothing is deleted: consents, imports, exports, packets and transmission records stay. RB-17 and
RB-19 cover a consent wave and a bridge failure while live.

## 4. go-live-check (tax level)

_Paste the JSON from the ops-task run here._
