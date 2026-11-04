# Supply-chain hygiene, quarterly (Q-03-T086; Q-03 §3.9 I2; ADR-099; DEC-366)

Acceptance (Q-03-T086, 2027 Q2): "No high or critical dependency or image finding is older than
its SLA at the quarter's end." The register is `docs/quality/supply-chain-findings.yaml`; the SLA
is critical 7 days, high 30 days, from the day first seen.

## Each quarter
1. **Findings to SLA.** `security.yml` runs pip-audit, bandit, Trivy (filesystem, IaC, the pinned
   base image) and CodeQL on every main push; `build.yml` records Inspector per image digest. A
   high or critical finding is fixed or entered in the register the day it is found.
2. **uv.lock refresh.** `uv lock --upgrade` in its own PR (the protected manifests: `uv.lock`,
   `pnpm-lock.yaml`), with `make check` and the replay histories green before merge (ADR-090: a
   Temporal SDK bump replays every recorded workflow history first, as #634 did for 1.35).
3. **Base-image digests.** The weekly base-image check (`build.yml` schedule) proposes the new
   digest; bump it in the same kind of PR.
4. **Evidence at quarter end.** `python -m abacus_tools.quality.supply_chain report --quarter
   <YYYYQn>` prints per source what was seen, closed and still open, and exits 1 if anything is
   past its SLA on the quarter's last day. Paste its output under the quarter below.

## Baseline (2026-10-29, ahead of 2027 Q2)
- `security.yml` on main `c441d80c`: pip-audit, bandit, Trivy (fs and base image), CodeQL (python,
  actions, javascript-typescript) all green. The one critical of the month, CVE-2026-115905 (the
  Rust `zip` crate inside temporalio's core), was fixed by #634 (temporalio 1.35.0) on the day it
  was raised to this session, so it never entered the register.
- bandit, high severity, `backend/src`: 0 findings (local run).
- `supply_chain report --quarter 2026Q4`: 1 bandit finding seen and closed (B613), 0 open, none
  past SLA.
- **Gap: Inspector.** `build.yml`'s Inspector step reads `scan status ''` for the new image: the
  scan never reports, so no `inspector.json` is written and no release is promotable. Enhanced
  scanning has to be on for the shared registry (`thirdparty/` and the app repository) before the
  first release; the staging stand-up owns it (DEC-1003, DEC-1007). Until then the image is
  covered by Trivy's image scan in `security.yml`, which is not the release gate.

## 2027 Q2
_Run `supply_chain report --quarter 2027Q2` on Jun 30, 2027 and paste the output here._

## 2027 Q4 (Q-03-T170, run 2026-11-03 on the plan's S26)
Local runs on the batch-merged tree (main f1b6c86ec plus the S26 batch-2 branches); CI's
`security.yml` has not run since Actions stopped creating runs on 2026-11-03 (recorded in
TASK-3240), so Trivy (fs, IaC, image), CodeQL and Inspector are not re-run here.
- **pip-audit** 2.9.0 on `uv export --locked` with hashes (as `security.yml`): no known
  vulnerabilities.
- **bandit**, high severity at medium confidence, `backend/src`: 0 findings.
- **pnpm audit** (high and above): 3 high, all js-yaml below 4.3.2 under `@hey-api/openapi-ts`
  (the API-client generator, build-time only): GHSA-52cp-r559-cp3m, GHSA-5p4m-2wfm-xmqj,
  GHSA-2883-xcg3-v3hh; 1 moderate below the bar. **Open, inside SLA** (high: 30 days, due
  2026-12-03). An override fixes them (tried: the generated client is byte-identical with js-yaml
  4.3.2), but `check_dependencies` refuses `overrides` and `pnpm-lock.yaml` is a protected
  manifest, so the fix is the protected-manifest PR below; pnpm cannot move the transitive pin on
  its own. The register takes them when CI's Trivy filesystem scan reports them (its sources do
  not include pnpm audit).
- **uv.lock refresh and base-image digests**: not done here; they need the protected-manifest PR
  with `make check` and the replay histories green, and the weekly digest check in `build.yml`.
- `supply_chain report --quarter 2026Q4`: every source 0 seen, 0 open; none past SLA.

## 2027 Q4 front end (Q-03-T181, run 2026-11-04 on the plan's S27)
- **pnpm audit --prod**: 0 findings (no runtime dependency carries an advisory).
- **pnpm audit (all)**: the 3 high js-yaml findings under `@hey-api/openapi-ts` (build-time only;
  GHSA-52cp-r559-cp3m, GHSA-5p4m-2wfm-xmqj, GHSA-2883-xcg3-v3hh) and 1 moderate (minimatch,
  GHSA-g3hv-75wg-m249, below the bar) stand as Q-03-T170 recorded them: **open, inside SLA**
  (high due 2026-12-03); the fix is still the protected-manifest PR (pnpm cannot move the
  transitive pin, and `check_dependencies` refuses `overrides`).
- **Pinned tool versions**: `pnpm-lock.yaml` holds `@playwright/test` and `playwright` 1.64.1,
  `@axe-core/playwright` and `axe-core` 4.13.0, `@fontsource/geist` 5.3.0. The parity manifest's
  `tools` still records Playwright **1.63.0**: drift. Per Q-03-T152's rule the parity rows are
  re-measured with 1.64.1 before the manifest moves; that run is the S27 end pass's parity step
  (Q-03-T186), and the manifest is not edited here.
- **Dependency bumps**: none this quarter outside the protected-manifest PR above.
