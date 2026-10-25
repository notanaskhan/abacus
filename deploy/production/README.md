# Production change records (Q-01-T34)

Production changes only through pull requests to this directory. The PR is the change record (SOC 2 CC8.1); under the solo amendment the builder approves it (`docs/plan/AMENDMENT-solo.md`).

## `release.json`: what production runs

`make release-pr SHA=<git sha>` copies the release record that `build.yml` wrote for that SHA (`s3://abacus-shared-artifacts/releases/<sha>/release.json`) into this file and opens a PR. Merging it runs `deploy-production.yml`, which refuses unless:

- staging verified this exact git SHA and image digest with a green deploy smoke (`releases/<sha>/staging-verified.json`);
- the SHA's workflow replay tests passed (`releases/<sha>/replay.json`, ADR-090);
- Inspector found no fixable critical or high finding in the image (`releases/<sha>/inspector.json`), or this file records an exception: `"inspector_exception": {"reason": "...", "finding_ids": ["..."]}` naming every such finding;
- if `infra_sha` differs from production's current release, the builder applied `infra/envs/production` by hand first and records it: `"infra_applied_sha": "<the same infra_sha>"` (SPEC-050 AC-6; no workflow holds apply).

Every value is a digest: the image `sha256:` digest, the SPA manifest's SHA-256, the Alembic head, the OpenAPI document's SHA-256 and the infrastructure's git tree. No tag. The committed file starts as a placeholder (`git_sha` null), which deploys nothing.

Cadence: at most one promotion a week, Thursday 10:00 CT, plus milestone releases. Batch: one release PR carries a whole merge window's work.

## Rollback

`rollback.yml` (workflow_dispatch, environment and reason) re-points the previous image digest and SPA bundle within 15 minutes. It never downgrades a migration: migrations are expand-only within a release (P-38). RB-01 has the steps.

## `ops-requests/`: operator commands in production

See `ops-requests/README.md`.
