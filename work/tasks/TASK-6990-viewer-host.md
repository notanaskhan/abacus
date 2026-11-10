---
id: TASK-6990
title: "The API reads the viewer's host behind the CloudFront edges"
spec: SPEC-050  # AC-24: CloudFront forwards Host as X-Forwarded-Host; a branding hint only
acceptance_criteria: [AC-24]
risk_zone: red  # api/middleware.py (PROTECTED), identity pinning
status: in-review
branch: fix/viewer-host-forwarded
worktree: /Users/ayushkbhatia/Accrued/abacus-viewer-host
created: 2026-11-10
updated: 2026-11-10
---

## Objective
Behind the portal and firm CloudFront edges the request's `Host` is the internal ALB's name; the
viewer's host arrives only as `X-Forwarded-Host`. Read that, from the load balancer only, at every
host-dependent site, and judge it in `TrustedHosts`. Found by the A-02-T33 security review
(TASK-6902, DEC-3902). Must land before the staging portal edge is deployed.

## Plan (red: edge middleware, identity pinning)
- `kernel/viewer_host.py`: `host_name`, `ProxyPeers` (uvicorn's trust rule), `resolve_viewer_host`,
  `viewer_host(request)` and the `ViewerHost` dependency; `SCOPE_KEY`.
- `api/middleware.py`: `TrustedHosts(allowed, proxies)` judges the viewer host and keeps it on the
  scope; `_host_name` moves to the kernel. `api/app.py`: `TrustedHosts` outermost, outside
  `ProxyHeadersMiddleware` (it must see the real peer).
- Sites: `portal/contract.py` (branding, logo), `identity/portal_auth_routes.py` (7 routes),
  `identity/routes.py` (invitation preview), `communications/secure_link_routes.py`,
  `identity/routing.py` (`portal_context`, `portal_invitee`), `connections/routes.py`,
  `integrations/routes.py` (`origin_host`).
- Edge: `cloudfront-firm/firm-edge.js` writes `X-Forwarded-Host` on `/v1/*` and drops a viewer's
  own; associated with both `/v1` behaviors. Staging: `ABACUS_PORTAL_BASE_DOMAIN` once set.
- No migration, no matrix, flag or registry change. The OpenAPI document loses the `host` header
  parameters (regenerated client).
- Docs: DEC-3990; ADR-163 amendment (viewer host); ADR-152 one-line amendment (DEC-3902 clause);
  kernel README.
- Tests first: `tests/unit/kernel/test_t6990_viewer_host.py`,
  `tests/acceptance/test_t6990_viewer_host_edge.py`,
  `tests/security/test_t6990_viewer_host_behind_edge.py`,
  `tests/integration/backfill/test_t6990_viewer_host_origin.py`, `infra/tests/test_firm_edge.py`.
- Rollback: revert the commit (the firm edge function and the API change together; the API with
  the old edge would trust a viewer-sent `X-Forwarded-Host` on the firm app).

## Progress log
- 2026-11-10: tests written first; built. Targeted runs: new unit, acceptance, security,
  integration and infra tests green; Q-01-T24 edge suite, `tests/unit/{api,quality,identity,portal,
  connections,integrations,communications}`, `tests/contracts`, and the portal sign-in, branding,
  invitations, recovery, pinning, scope isolation and route introspection suites green, except
  main-owned reds: `test_c16_kinds` (#1589), `validate_docs` (TASK-5901 spec field),
  `banned_patterns` (t6960 `noqa`), a02t33's portal-session test (201 since DEC-3960; flip
  403 -> 201 is DEC-3960's follow-up), and a02t33 / t6960 colliding on one worker's catalog
  (`connector_provider` `fake` loaded under two keys). Web typechecks on the regenerated client.
- Mistake caught by a test: an empty `Host` became "no host" and was refused under `*`
  (test_portal_branding); kept as `""`.
- Follow-ups: staging's ALB `/readyz` health check sends the target IP as `Host`, which
  `trusted_hosts` (the firm edge name only) refuses; list the app subnets' CIDRs in
  `ABACUS_TRUSTED_HOSTS` or give the check a trusted host before deploying (DEC-3990 Open).
  The firm app's `app.<domain>` alias joins `trusted_hosts` with the firm domain (DEC-3901).
