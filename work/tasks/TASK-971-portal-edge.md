---
id: TASK-971
title: Portal edge - multi-tenant distribution, wildcard default host, canary custom-domain tenant, WAF auth and code rate rule, portal-entry deploy path (Q-01-T56)
spec: SPEC-050
acceptance_criteria: [AC-23, AC-24]
risk_zone: red
status: in-review
epic: Q-01
plan_key: Q-01-T56
branch: s5-ops-closeout
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The canary custom host serves the portal entry with its own certificate on the same /v1 origin, and the 31st auth request in 5 minutes from one IP is blocked" (Q-01-T56; OPS-14 part; D-OPS-10; ADR-163; Q-01 F4).

## Plan
- `infra/modules/waf` (was a skeleton): a CloudFront-scope WebACL, resources in us-east-1 through the resource `region` argument.
  - Rule 0: `auth-and-code-rate`, 30 per 300 s per IP on `^(?:/v1/auth/|/v1/portal/auth/)`, after URL decoding and lower-casing. Always block, with 429 `{"detail": "rate_limited"}`.
  - Rule 1: general rate, 2,000 per 5 minutes.
  - Rules 10 to 40: the managed groups, in count or block mode. The common set counts `SizeRestrictions_BODY`, and a label rule blocks oversized bodies outside upload routes. Anonymous IPs are count only.
  - Logging redacts `authorization` and `cookie` once a log-archive Firehose exists.
- `infra/modules/cloudfront-portal` (was a skeleton):
  - `aws_cloudfront_multitenant_distribution` with the bundle bucket (OAC, SSE-KMS, TLS-only, versioned) and the API's VPC origin;
  - behaviours: `/assets/*` cached for a year, `/v1/*` uncached with every viewer header but `Host`, and everything else uncached;
  - the `portal-entry.js` viewer-request function;
  - the portal security-headers policy, with the build's CSP as a header;
  - a wildcard ACM certificate for `*.<portal_base_domain>`;
  - tenant `default` (`*.<portal_base_domain>`), and tenant `canary` with a CloudFront-managed certificate, only when its domain is set;
  - the SSM parameter `/abacus/<env>/runtime-config/portal_base_domain`;
  - a managed deploy policy for the deploy role.
- `infra/envs/staging/portal_edge.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example`: both modules, gated by `count` on `portal_base_domain`, `api_vpc_origin_id` and `api_origin_domain_name`. Each defaults to null, so staging plans to nothing until the builder sets them.
- `kernel/config.py`: settings refuse a `portal_base_domain` containing the product name (ADR-163 enforcement list).
- Tests first: `infra/tests/test_portal_edge.py` (offline: the Terraform text, and the entry function under node) and two cases in `tests/unit/kernel/test_config.py`.
- Rollback: unset the three tfvars values and apply (count goes to 0), or revert the commit. No other root reads these modules.

## What changed
- As planned. 42 offline tests:
  - the rate rule's limit, window, key and action;
  - the auth paths, against the portal identity contract's routes;
  - the WebACL attached to the distribution;
  - the multi-tenant distribution with a wildcard default tenant and a managed-certificate canary tenant on the same distribution;
  - `/v1/*` to the VPC origin, uncached;
  - TLS 1.2 and the portal headers;
  - the CSP header equal to `vite.config.ts`'s;
  - the entry function: routes go to `portal.html`, files pass through, probes get 403, and `X-Forwarded-Host` is the viewer's host, never a forged one;
  - no domain literal and no product name in the portal edge files;
  - the off-by-default gate;
  - the deploy path matching the portal build's layout;
  - the runtime-config parameter.
- No invalidation is needed: the entry files are never cached at the edge.
- The deploy policy has no `DeleteObject`, so old hashed assets stay for rollback.
- Deviations: the firm distribution and its WebACL stay Q-01-T15's. Rule 6's POR-17 respondent code verification has no route yet, so its prefix is a variable to extend when it lands.
- AWS WAF rate rules act a few seconds after the limit is crossed. The live check accepts "the 31st, give or take that lag" (`infra/README.md`).

## Not done (needs the builder)
- `terraform apply` on staging. No session runs it.
- The neutral portal domain registered (F-09-T09), with its hosted zone in `shared`.
- Q-01-T15's internal load balancer and VPC origin, which this edge needs.
- The certificate's validation CNAME; the wildcard CNAME to the connection group.
- A canary domain you control, with its CNAME. A domain may need buying.
- Attaching the deploy policy to the deploy role (Q-01-T18).
- The live checks: two certificates, same-origin `/v1`, and 429 on the 31st request.
- Steps: `infra/README.md`, "Portal edge".

## Progress log
- 2026-10-23: `terraform fmt -check -recursive infra` passes. `terraform validate` passes on `envs/staging` after `init -backend=false`, with no credentials, no plan and no apply. `infra/tests` passes (126 passed, 1 skipped as before: no plan JSON). The kernel config tests pass. `tflint` and `trivy` are not installed locally, so they run in `infra.yml` on the PR.
