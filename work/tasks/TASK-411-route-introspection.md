---
id: TASK-411
title: Generated security tests part 2 - route introspection and the security stage (Q-02-T15)
spec: SPEC-050
acceptance_criteria: [AC-24]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T15
branch: q02-t15-route-introspection
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"By Fri Dec 11 the security check is required on main and a route without an action fails it."
(Q-02-T15; Q-02 AC-46; ADR-012, ADR-027, ADR-152, P-45.)

## Plan (red)
- Generated, as Q-02 §4.10 requires ("generated; regenerate, never hand-merge"):
  `abacus_tools/codegen/security_tests.py` gains `served(app)` and renders
  `backend/tests/security/test_route_introspection.py` from `create_app()`: one row per
  (method, path, declared action) built by `AbacusRouter` and one per route answering without a
  token. Already in `GENERATORS`, so `make check-generated` fails on a hand edit or on a route
  added without regenerating.
- Hand-written checks in `backend/tests/security/route_checks.py`:
  - `route_problems`: an `AbacusRoute`, exactly one declared action, the action in
    `identity.api.RULES` or a route marker (SELF, STAFF, OWN, IDENTITY), a response model (or
    204), and exactly the authentication dependency that action needs (`current_context` for a
    matrix action; the marker's own otherwise).
  - `public_problems`: every unauthenticated route is on `PUBLIC_ROUTES` and on the protected
    `PUBLIC_ROUTE_EXCEPTIONS` (ROUTE-001), GET only, out of the OpenAPI document; every listed
    path is served.
  - `openapi_problems`: a second source. Every OpenAPI operation names the generated action.
- Meta-test `test_route_introspection_detects.py`: a route without an action, an action outside
  the matrix, no response model, a route outside the router, a public path answering POST or
  appearing in the document: each is reported; a well-formed route is not.
  `tests/unit/tools/test_security_tests_codegen.py`: a hand edit to the new file fails `--check`.
- Neither security file needs a database: each overrides the security conftest's autouse
  `engines` fixture, so no container starts.
- CI: new `.github/workflows/security.yml` (there was no security workflow): CodeQL (python,
  javascript-typescript, actions; security-extended), dependency review (PRs, fail on high),
  pip-audit 2.9.0 over the hashed `uv export` of `backend/uv.lock`, Trivy fs (vuln, HIGH and
  CRITICAL, fixed only). Actions pinned to full SHAs; no secrets; `security-events: write` only
  on the CodeQL job.
- Rollback: revert the commit.

## What changed
- `backend/src/abacus_tools/codegen/security_tests.py`: `served()`, `render_introspection()`, the
  third target.
- `backend/tests/security/test_route_introspection.py` (generated): 295 routes, 2 public.
- `backend/tests/security/route_checks.py`, `backend/tests/security/test_route_introspection_detects.py`.
- `backend/tests/unit/tools/test_security_tests_codegen.py`: INTROSPECTION added.
- `.github/workflows/security.yml`.

Findings: no route violates the rule. All 295 API routes are `AbacusRoute`s with one action from
the matrix or a marker, a response model and the matching authentication; the only
unauthenticated routes are `GET /healthz` and `GET /readyz`. No known-violations set was needed.

pip-audit on today's lock finds 35 advisories in 2 packages: pillow 12.3.0 (34, fixed in 13.0.0)
and certifi 2026.7.22 (1, fixed in 2026.10.19). Dependabot PRs #185 (pillow) and #186
(certifi) fix both; `security pip-audit` (and likely `security trivy`) stay red until they merge.

## Manual step for the owner: make the stage required
Rulesets and branch protection are repository settings, changed by hand (AMENDMENT-solo §4;
not done by this task). Before R1 (Fri Dec 11), in Settings, Rules, Rulesets, the `main` ruleset
(F-01-T06), under "Require status checks to pass", add these check names exactly:

- `security codeql (python)`
- `security codeql (javascript-typescript)`
- `security codeql (actions)`
- `security dependency review`
- `security pip-audit`
- `security trivy`

The generated suites (`test_tenant_isolation.py`, `test_permission_matrix_generated.py`,
`test_route_introspection.py`) run inside `stage 2 integration tests (1/5)` … `(5/5)` in
`ci.yml`; those check names should be required too if they are not already. Merge #185 and #186
first so the new checks are green.

## Definition of done
- [x] `test_route_introspection.py` generated: 298 cases pass, no container
- [x] Meta-tests pass; a hand edit fails `--check`
- [x] ruff, pyright, banned_patterns, `make check-generated`, validate_docs
- [ ] Ruleset makes the security stage required (owner, by hand; above)

## Progress log
- 2026-10-22: built in one session. The detect test first caught FastAPI's default `/docs`,
  `/redoc` and `/openapi.json` on a bare `FastAPI()`: the check sees them as unauthenticated
  routes off the list, as it should; `create_app()` disables all three.
