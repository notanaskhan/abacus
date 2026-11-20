---
id: TASK-8759
title: "G-04-T22: Rollout and close-out: console host and WAF IP allowlist, security review and Nov 2028 delta pen-test scope, flag renewal ticket and flips, RB-12 update and new console, status and support runbooks, capacity ledger"
spec: SPEC-681
acceptance_criteria: [AC-15]
risk_zone: red
status: in-review
branch: s51-g04t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: G-04-T22
---

## Objective
The console is reachable only from the allowlist with staff SSO and MFA on staging, the flip and renewal tickets carry written rollbacks, and the runbooks merge.

## Plan (red)
1. Terraform: `modules/waf` `allow_ipv4_cidrs` (an IP set and a priority-4 block-everything-else rule, nothing when empty); `modules/cloudfront-firm` `default_root_object` (index.html default, console.html for the console); `modules/s3-web` `extra_distribution_arns`; `envs/staging/console_edge.tf` gated on console_host, console_certificate_arn and console_allow_ipv4_cidrs (untracked tfvars).
2. Tests: `infra/tests/test_console_edge.py` (the rule blocks outside the set, exists only with CIDRs, the default action is the only allow, the edge is off until all three are set, no CIDR committed, the firm edge keeps index.html).
3. Runbooks: RB-12 section on firm-content support sessions after G-04; RB-95 staff console; RB-96 support panel and status.
4. `docs/plan/status/G-04-rollout.md`: security self-review, the deferred delta pen-test scope (DEC-1389), the flag renewal ticket and the canary and firm flips, each with a written rollback, and the capacity line.
5. Rollback: revert the PR; nothing is applied from it.

## Progress log
- `2026-11-20` — Built, stacked on #2397; `terraform validate` on staging passes; console-edge and firm-edge infra tests 21 pass; validate_docs passes. Not done (the builder's, by hand): the console domain, certificate and CIDRs, `terraform apply`, deploying dist/console, and the staging check that only the allowlist reaches the console with staff SSO and MFA; the renewal and flips are tickets on paper for their train dates; the pen test is deferred. Found: `infra/tests/test_portal_edge.py` has 13 failures on the base too (it pins the auth-path regex before A-08-T38 added the confirmation code route); left as is. Gates and tests run once at the S51 end pass (build first, test last).
