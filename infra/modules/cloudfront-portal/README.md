# cloudfront-portal

The client portal edge (Q-01-T56, OPS-14 part; D-OPS-10; ADR-163). Used by `envs/staging/portal_edge.tf`; production gets the same module with Q-01-T28's production root.

| Resource | What it is |
|---|---|
| `aws_cloudfront_multitenant_distribution.portal` | One distribution for every portal host. Origins: the bundle bucket (OAC) and the internal API load balancer through a VPC origin. Behaviours: `/assets/*` cached for a year; `/v1/*` uncached, every viewer header but `Host`; everything else uncached. WebACL from `modules/waf`. TLS 1.2 minimum, SNI |
| `aws_cloudfront_distribution_tenant.default` | `*.<portal_base_domain>`: every firm's default host, on the distribution's wildcard ACM certificate (us-east-1) |
| `aws_cloudfront_distribution_tenant.canary` | One firm custom domain (pen test 1) with its own CloudFront-managed certificate. Only when `canary_custom_domain` is set |
| `aws_cloudfront_function.entry` (`portal-entry.js`) | Viewer request: `/healthz` and `/readyz` answer 403; `/v1/*` gets `X-Forwarded-Host` from the viewer's `Host` (a branding hint only, INV-4; a forged one is replaced); portal routes at the origin root get `portal.html` |
| `aws_cloudfront_response_headers_policy.portal` | HSTS 2 years with subdomains, `nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Permissions-Policy: camera=(self), microphone=(), geolocation=()`, and the build's CSP as a header |
| `aws_s3_bucket.portal` | `abacus-<env>-web-portal`: private, TLS-only, versioned, SSE-KMS with its own key; replaced entry files kept 30 days for rollback |
| `aws_ssm_parameter.portal_base_domain` | `/abacus/<env>/runtime-config/portal_base_domain`, read by the deploy when it renders `runtime-config.json` |
| `aws_iam_policy.deploy` | `abacus-<env>-portal-deploy`: list and put `assets/*`, `portal.html`, `runtime-config.json`; read the runtime-config parameters. The deploy role (Q-01-T18) attaches it |

Rules:

- No domain is written here. `portal_base_domain` and `canary_custom_domain` come from the untracked tfvars, and both refuse the product name (ADR-163 section 2).
- New custom domains are new tenants on this distribution (R-01, ADM-10), never new distributions.
- The tenant never comes from the host. The API reads `X-Forwarded-Host` for branding only (ADR-163 section 5).
- No invalidations: the entry files are never cached and assets are content-hashed.

Deploy path, apply order and checks: `infra/README.md`, "Portal edge". Offline tests: `infra/tests/test_portal_edge.py`.
