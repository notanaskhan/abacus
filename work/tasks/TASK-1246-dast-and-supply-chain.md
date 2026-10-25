---
id: TASK-1246
title: Weekly DAST baseline of staging (Q-03-T004) and supply-chain hygiene 2027 Q1, findings to SLA (Q-03-T029)
spec: SPEC-045
acceptance_criteria: [AC-4]  # the security stage runs on push and PR; T004 and T029 are Q-03 §3.4 D4 and §3.9 I2 (no spec AC of their own)
risk_zone: red
status: in-progress
epic: Q-03
plan_key: Q-03-T004; Q-03-T029
branch: s8b-quality
created: 2026-10-25
updated: 2026-10-25
---

## Objective
T004: "The first baseline runs against staging with no high alert open before the Fri Feb 12, 2027
build pin." T029: "No high or critical dependency or image finding is older than its SLA at the
quarter's end."

## Plan (red zone)
- **Allowlist PR:** `zaproxy/zap-stable` under `containers:` with its reason (DEC-366), pinned by
  digest to a release at least two weeks old.
- **`dast.yml` (new):** weekly ZAP baseline of staging; skips itself while a staging deploy runs or
  waits; holds the `staging-deploy` concurrency group; counts only in the public log; report
  encrypted to the founders' key; a high alert opens or updates a SEV3 issue and fails the run.
  Off until `STAGING_DAST=on`.
- **`abacus_tools.quality.dast`:** counts a ZAP JSON report by risk; prints nothing else.
- **Supply chain:** `docs/quality/supply-chain-findings.yaml` and
  `abacus_tools.quality.supply_chain` (SLA critical 7 days, high 30; `check` and `ignores`);
  security.yml gains bandit, a Trivy scan of the pinned base image, the SLA ignores for pip-audit
  and Trivy, and a `findings SLA` job.
- **Tests:** `tests/unit/quality/test_dast_triage.py`, `tests/unit/quality/test_supply_chain.py`,
  `tests/unit/tools/test_security_scan_workflows.py`, `tests/unit/tools/test_dast_workflow.py`.
- **Rollback:** revert; the allowlist row goes with it.

## Progress log
- 2026-10-25: built. Local scans: bandit 1.9.4 (in the lock) over `backend/src` found one high,
  B613 (literal bidi characters in `abacus_tools/synthetic/adversarial.py`), fixed with escapes
  (ED-057; recorded closed in the register); no high remains. The one medium (B604 in
  `platform/routes.py`) is a false positive: a `shell=` keyword that names the portal shell.
  **Not run here (installs or downloads need Ayush's go-ahead):** pip-audit (runs through `uvx`
  in CI), Trivy (fs, IaC, image), CodeQL and Inspector, `uv lock --upgrade` (the lock refresh),
  the base-image digest bump, and the ZAP image itself. The ZAP digest was read from Docker Hub's
  tag API (20261008, Oct 8 2026, index digest); verify it with `docker buildx imagetools inspect`
  before the first run.
  **Human to-dos:** set `ABACUS_STAGING_URL`, `DAST_REPORT_KEY` (an ASCII-armoured public key of
  the founders) and `STAGING_DAST=on` once staging is up; give `deploy-staging.yml` the
  `concurrency: staging-deploy` group when it is written; make the new security jobs required if
  wanted (ruleset). T004's acceptance (first baseline on staging before Feb 12) and T029's (no
  finding past SLA at the quarter's end) are dated and wait on staging and the quarter.
  Tests: `pytest tests/unit/quality/test_dast_triage.py tests/unit/quality/test_supply_chain.py
  tests/unit/tools/test_security_scan_workflows.py tests/unit/tools/test_dast_workflow.py`: 24
  passed.
- 2026-10-26: security review fixes: dast.yml split into an unlocked `preflight` (switch and
  deploy-in-flight check, failing closed) and the locked `baseline`; the high count reaches the
  shell through env; on pull requests the scanners' ignores come from the base's register and
  `check --base-register` refuses a loosened one; the register is human-only for agents. DEC-366
  amended.
