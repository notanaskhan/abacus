---
id: TASK-916
title: Sub-processor register, generated Markdown and the Terraform egress drift check (Q-01-T51)
spec: SPEC-050
acceptance_criteria: [AC-22]
risk_zone: amber
status: done
epic: Q-01
plan_key: Q-01-T51
branch: TASK-916-sub-processor-register
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The register lists AWS, Temporal, WorkOS, Sentry and Better Stack with regions and DPA status, and a check fails if an egress host in Terraform has no register row" (Q-01-T51; P-67, ADR-154; chapter 06 section 6.9).

## Plan
- `docs/operations/sub-processors.yaml`, the source:
  - one row per party in chapter 06 section 6.9, with `kind` (sub-processor, integration, operations, egress-only), role, data seen, `client_data`, region, a `dpa` status, needed-by, `egress_hosts` and ADR or DEC references;
  - DPA status words only, with no contract terms and no prices (the repository is public).
- `abacus_tools.codegen.sub_processors`:
  - validates every row and writes `docs/operations/sub-processors.md` for the vendor-diligence pack;
  - added to `GENERATORS`, so `make check-generated` (in `check-fast`) runs it with `--check`;
  - the drift check: every string in a `domains = [...]` list (the DNS Firewall allowlist of AC-22) or in a `*_domains` / `*_hosts` list in `infra/**/*.tf` must be covered by a row's `egress_hosts`. Exact matches count, and a `*.suffix` row covers subdomains only.
- The generated Markdown is listed with the generated files in `protected-paths.md` and `.claude/hooks/_protected.py`. The YAML is listed with the policy files that still bind.
- Tests: `backend/tests/unit/quality/test_sub_processors.py`.
- Rollback: revert the commit; nothing else reads the register yet. ADM-04 (G-02) and the section 7216 recipients will read it.

## What changed
- As planned. 11 tests:
  - the five named vendors carry a region and a DPA status;
  - the register and its Markdown are current;
  - a Terraform host with no row fails, and the check names the host and the file;
  - named host lists count, while comments and interpolations do not;
  - the wildcard semantics hold;
  - a malformed DPA status is refused, and so is a party that sees client data while marked `not-required`.
- The DNS Firewall module is still a skeleton, so no Terraform host exists today and the check passes trivially until Q-01-T14 or T15 writes the allowlist. The rows already carry the AC-22 allowlist hosts: Temporal Cloud, WorkOS, the Sentry US ingest, Better Stack, `database.clamav.net` and `api.anthropic.com`.
- Every `dpa` is `to-confirm` for the parties that need a DPA. Change a row to `signed` once its DPA is confirmed for the account (F-09 vendor paperwork).
- Regions marked "to verify" are carried over unchanged from chapter 06 section 6.9.

## Progress log
- 2026-10-23: the new tests, `make check-generated`, `validate_docs`, `secrets_scan`, ruff and pyright on the new files all pass.
