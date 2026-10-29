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
