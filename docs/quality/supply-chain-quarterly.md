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

## 2027 Q3 (Q-03-T148, run 2026-11-12 on the plan's S23; DEC-4802)
Local runs on main 17a7ffc64 plus this branch; CI's `security.yml` is green on main (43229903561,
fa5de4306; 43224679728, 5c142ff0c): pip-audit, bandit, Trivy (fs, IaC, the pinned base image)
with the register's in-SLA ignores.
- **pip-audit** 2.9.0 on `uv export --locked --no-emit-project` with hashes (as `security.yml`):
  no known vulnerabilities.
- **bandit**, high severity, `backend/src`: 0 findings.
- **CodeQL** (GitHub code scanning, open alerts read 2026-11-12): 21 high, 3 medium. None was in
  the register. Triaged each:
  - **Fixed, 3** (TASK-7805; registered as closed): the polynomial regexes in
    `evidence/export_download.py` (the `Range` header, alert 21), `reporting/templates.py`
    (`has_markup`, alert 24) and `assurance/governance_comms.py` (the amount check, alert 27).
    Measured quadratic on CodeQL's attack strings (0.2 s to 0.8 s at 20,000 characters, ×4 per
    doubling); now linear and accepting exactly the same inputs
    (`backend/tests/unit/quality/test_q03t148_linear_regexes.py`: property tests against the old
    patterns and a time bound at 200,000 characters). CodeQL closes them on its next main scan.
  - **False positives, 18, to dismiss in code scanning** (not registered: a registered finding
    is a real one):
    - `py/polynomial-redos` alerts 7 (`communications/scope.py`) and 8
      (`communications/templates.py`): measured linear on CodeQL's strings.
    - `py/path-injection` 25, 26 (`tax/compute/payments.py`): the path is the package's own
      directory and `ty<int>.yaml`; `tax_year` is an `int`.
    - `py/weak-sensitive-data-hashing`: alert 20 is a content fingerprint (`storage.fingerprint`,
      SHA-256 of file bytes). Alert 11 hashes random 32-byte tokens (`portal_session.sha256_hex`).
      Alerts 18 and 19 are the PDF standard-security MD5 that ISO 32000-1 requires, for synthetic
      fixtures (`usedforsecurity=False`). Alert 12 is a test. None hashes a password.
    - `py/incomplete-url-substring-sanitization` 9, 17, 23: assertions in tests.
    - `js/regex/missing-regexp-anchor` 3 to 6: tests asserting no Google Fonts URL appears.
    - `js/file-system-race` 1, 2: `apps/web/scripts/seed-manifest.mjs`, a local dev script.
  - Medium (below the bar): 28 `py/url-redirection` (`portal/approvals_contract.py`) is a redirect
    to a path under the route's own prefix (it starts with `/v1/`, never `//`); 10 and 22
    `py/overly-large-range`.
- **pnpm audit** (high and above): the same 3 high js-yaml advisories under `@hey-api/openapi-ts`
  (GHSA-52cp-r559-cp3m, GHSA-5p4m-2wfm-xmqj, GHSA-2883-xcg3-v3hh; build-time only). **Open,
  inside SLA (due 2026-12-03).** Upstream has no fix: `@hey-api/json-schema-ref-parser` 1.4.4,
  its latest, still pins `js-yaml` 4.2.0 exactly. The only fix is a `pnpm.overrides` pin, which
  `check_dependencies` refuses. Needs a decision before Dec 3: allow an override for a security
  pin, or accept the build-time risk.
- **Base image** (CVE-2026-76844, CVE-2026-85091, zlib1g): **open, inside SLA (due
  2026-12-07)**. The runtime stage already upgrades zlib1g (`backend/Dockerfile`), so only the
  base layer carries it. Upstream has moved on (`python:3.12-slim@sha256:5e2bdb1b…` on
  2026-11-12). The weekly refresh (`build.yml` base-refresh) found a new digest on Oct 26, Nov 2
  and Nov 9 and pushed `base-refresh-2026110{2,9}` branches, but it fails to open its PR: "GitHub
  Actions is not permitted to create or approve pull requests". Fix: allow it in the repo's Actions
  settings, or open the PR from the latest refresh branch by hand. Then check the Dockerfile's
  pinned renderer libraries against the new base, and Trivy re-scans it.
- **uv.lock refresh**: not done here (a protected-manifest PR with `make check` and the replay
  histories green).
- **Inspector**: still not reporting (the 2026-10-29 baseline gap; no staging registry scan).
- `supply_chain check`: 2 open findings (the zlib1g pair), none past SLA on 2026-11-12. On the
  real quarter's last day both would be past SLA unless the base digest moves first.

Acceptance ("no high or critical dependency or image finding older than its SLA at the quarter's
end") is met as of 2026-11-12. It stays met only if the js-yaml decision lands by Dec 3 and the
base digest is refreshed by Dec 7.

## 2028 Q2 (Q-03-T268, run 2026-11-12 on the plan's S40)
Local runs on the S40 stack (main 09639107a plus the S40 branches #1812–#1849). CI's
`security.yml` runs once, on the batch's last merge; Trivy (fs, IaC, image) and Inspector need
built images and are not re-run here.
- **pip-audit** 2.9.0 on `uv export --locked` with hashes: no known vulnerabilities.
- **bandit**, high severity at medium confidence, `backend/src`: 1 finding, **B613** (trojan
  source) in `platform/search/scrub.py`, P-02-T06's hostile-character pattern written with literal
  bidi and zero-width characters. Fixed the same day as escapes (same character set, asserted);
  P-02-T06/T07's two tests that carried literal bidi characters in strings are escaped too.
  Re-run: 0 findings. Register: B613 (scrub.py) seen and closed 2026-11-12.
- **pnpm audit** (high and above): the 3 high js-yaml findings under `@hey-api/openapi-ts`
  (build-time only; GHSA-52cp-r559-cp3m, GHSA-5p4m-2wfm-xmqj, GHSA-2883-xcg3-v3hh) still stand.
  They are due 2026-12-03 and need the protected-manifest override PR, which is the user's call.
- **CodeQL** (open alerts, read through the API): 3 medium, below the high/critical bar, all false
  positives:
  - #28 `py/url-redirection` in `portal/approvals_contract.py`: a same-origin path from the
    router prefix and a registered kind.
  - #22 and #10 `py/overly-large-range`: deliberate control-character ranges.

  Dismissing them in code scanning is the user's call.
- **Trivy image**: CVE-2026-76844 and CVE-2026-85091 (zlib1g in the pinned
  `python:3.12-slim` digest) are due **2026-12-07**. `supply_chain report --quarter 2026Q4` says
  they pass their SLA unless the base digest is bumped first, so the digest-bump PR has to land
  before Dec 7.
- **uv.lock refresh and base-image digests**: not done here. Both are protected-manifest PRs that
  need `make check` and the replay histories green.
