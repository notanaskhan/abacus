---
id: ADR-152
title: Unauthenticated operational routes - /healthz and portal branding on an explicit allowlist
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
**Accept by 2026-11-13.** `AbacusRouter` refuses any route without a matrix action. A load balancer needs `/healthz`, and a portal visitor needs branding before sign-in. Plan decision DEC-59 names `GET /v1/portal/branding` and `/healthz` as the only unauthenticated routes; this ADR is P-45, drafted under Q-01-T10 and built under Q-01-T16. Without it, these routes would bypass the router ad hoc.

## Decision
- **Two allowlisted unauthenticated routes**, outside `AbacusRouter`, on the ROUTE-001 exception list: `/healthz` and `GET /v1/portal/branding`.
- **Portal branding and its logo** (`GET /v1/portal/branding`, `GET /v1/portal/branding/logo`, P-08-T05; ADR-163 §6, P-08 OQ-2): on the same exception list, but served inside `AbacusRouter` under the `PORTAL_PUBLIC` route marker, which the router accepts on those two paths only (as ADR-165's `PRE_SESSION` for the staff sign-in routes). They are in the OpenAPI document, so the portal's generated client types them.
- **The list is explicit and checked by ROUTE-001** (a protected banned pattern); any other route without an action still fails.
- **The portal host is only a branding hint.** `/v1` is proxied same-origin.
- **`/readyz`** is added under Q-01-T16 on the same list; later proposals (P-01, P-08) extend the list through their own ADRs.

## Options considered
### Option A: explicit allowlist on the ROUTE-001 exception list — chosen
- Pros: the exception is visible and testable.
- Cons: every new public route needs an ADR.

### Option B: give the routes a matrix action
- Pros: no exception.
- Cons: an action needs a principal, and these have none.
- Why rejected: not adopted by the plan.

## Consequences
**Positive**
- No hidden unauthenticated route.

**Negative / costs accepted**
- Branding responses must carry no client data.

**Follow-up work created**
- Code: `/healthz` and `/readyz` routes and middleware (Q-01-T16, S1); independent tests (Q-01-T24, S1).
- Specs: POR-*, ADM-10, POR-20, SHL-06 (EP-02, EP-07, EP-19).
- Glossary: public route (`docs/product/glossary.md`).
- Matrix: none; the allowlist is the exception.
- Registry: ROUTE-001 exception list in `docs/architecture/protected-paths.md` and the lint config.

## Enforcement
- [x] Lint rule: ROUTE-001 fails any unauthenticated route not on the list.
- [ ] Architecture / dependency rule in CI: none.
- [x] Test: only listed paths answer without a token.
- [x] Hook or protected path: the exception list is protected.
- [ ] Reviewer agent checklist item: none.
- [ ] Advisory only — reason: n/a

## Guidance for agents
Do not add an unauthenticated route. Propose an ADR that extends the list.

**Do**
```
PUBLIC_ROUTES = ("/healthz", "/readyz", "/v1/portal/branding")
```

**Don't**
```
@app.get("/v1/anything")   # outside AbacusRouter
```

## Amendment: the DocuSeal webhook receiver (accepted 2026-10-30; N-02-T01, DEC-707, DEC-1281)
Proposed under N-02-T01 for DocuSign Connect, retargeted to DocuSeal by ADR-342 (DEC-1277), and accepted with this ADR.
- **A provider webhook receiver**, `POST /v1/webhooks/docuseal/{tenant_id}/{install_id}`, joins the ROUTE-001 exception list, unauthenticated, inside `AbacusRouter` under the `PROVIDER_WEBHOOK` marker, which the router accepts on that path only (as `PORTAL_PUBLIC` for branding). The path names the firm and its DocuSeal install: each install has its own webhook in DocuSeal and its own key, and the firm's rows are read under its own row security, so the receiver can find the key before trusting anything.
- **HMAC-verified** with the install's DocuSeal webhook key (sealed in the install's secret; DocuSeal's `whsec_…` used whole): `X-Docuseal-Signature` is `<unix seconds>.<hex HMAC-SHA256 over "<unix seconds>.<raw body>">`, compared in constant time against every configured key (rotation); a timestamp more than five minutes from now is refused as a replay; a bad, stale or missing signature, an unknown or disconnected install, W7 closed or the firm's kill switch off answers 401 and writes nothing but a metric (`status_poll.verify_webhook`).
- **Hint only:** the body is never trusted for state. A valid hint (`status_poll.webhook_event`: the submission id and a stable event id only, recorded once per event by `record_provider_hint`) signals the named envelope's workflow, which reads the provider's status and decides; the receiver itself changes no envelope row.
- **Rate-limited** per source (the edge's WAF rule on `/v1/webhooks/`) and per envelope (at most ten hints a minute); **echoes nothing** (an empty 202, 401 or 413); bodies and headers are not logged.
- **Without a webhook key** in the install, the firm runs poll-only (`EnvelopeStatusPoll` every 5 minutes for open provider envelopes, and on a portal return).

## Amendment: the connect host's hand-off (2026-11-10; A-02-T33, DEC-3902)
- **`POST /v1/connections/handoff`** joins the ROUTE-001 exception list, inside `AbacusRouter` under the `PRE_SESSION` marker (on `PRE_SESSION_PATHS`). The provider returns every firm's OAuth flow to one registered host, where no session is valid; this route tells that host's page where the flow began.
- **The OAuth state authenticates it.** It answers `{origin_host}` only for an unused, unexpired state whose stored host (the request's own `Host` at start, never the query) is the app host or an active portal host of the state's own firm; anything else is one 404. It names no tenant, firm or engagement and never spends the state; completion stays authenticated (`POST /v1/connections/complete`).
- No GET: the state stays out of request lines and logs.
- (2026-11-10; TASK-6990, DEC-3990) "The request's own `Host`" is the viewer host defined by ADR-163's viewer-host amendment: the load balancer's `X-Forwarded-Host` behind CloudFront, else `Host`.

## Amendment: public respondent access, the `/v1/confirm/*` family (accepted 2026-11-15; A-08-T02, DEC-5029, DEC-5052)
**Status of this amendment: accepted** on 2026-11-15 by ayushkbhatia (DEC-5052). Live `/v1/confirm/*` routes still answer only once A-08's services replace the S45 stub (A-08-T06 serves fixtures in local and test only). P-09 (ADR-146) already decides link principals; this amendment adds the concrete route family to the exception list, as A-08 §0.1 and OQ-2 direct (no new P-ID).
- **Five paths join the ROUTE-001 exception list**, inside `AbacusRouter` under a `LINK_PRINCIPAL` marker that the router accepts on these paths only (as `PRE_SESSION` and `PORTAL_PUBLIC`):
  `GET /v1/confirm/{token}` · `POST /v1/confirm/{token}/code` · `POST /v1/confirm/{token}/code/verify` · `POST /v1/confirm/{token}/attachments` · `POST /v1/confirm/{token}/response`.
  No other path may carry the marker; a new purpose (R-03 intake) is a further amendment.
- **The token authenticates the link principal, never a person.** The handler hashes the path token (SHA-256), resolves it only through the pinned `SECURITY DEFINER` function `identity_resolve_link(token_hash)` (the one pre-tenant read), and proceeds under that tenant's row security as `actor_kind = link_principal` with `link_scope_only`: it reads or submits exactly the one object the link names. The token travels in the path only; the access log and every log line redact it; it is never in a query string.
- **Uniform, padded answers (no enumeration).** Unknown, expired, revoked and kill-switched tokens answer the same status (200 with state `expired` on GET; 404 on POST), the same body and at least the same padded minimum duration (`CONFIRM_PAD_MS`, 400 ms, measured from receipt). `POST …/code` answers 202 after the padded minimum for any input and any address.
- **Email code.** Six digits, 10-minute expiry, hashed at rest (`link_principal_challenges.code_hash`); five wrong codes lock the link principal for 15 minutes (ADR-141's lockout mechanics, P-08-T10); a verified code upgrades the page credential (a `__Host-` cookie bound to the link principal, `SameSite=Strict`, CSRF double-submit), never a session.
- **Edge limits.** WAF rule 6 limits `/v1/confirm/*/code*` to 30 requests per 5 minutes per IP; the other confirm paths share the portal's per-IP rate.
- **Kill switch.** The `confirmation_links` platform control (ADR-157), per firm and global, is checked before any read or issuance: when active, every `/v1/confirm/*` call renders the expired answer and AUD-14 shows "Respondent links paused".
- **Single object, single answer.** The response is insert-only; a second submission answers 409 `already_answered` with the original receipt id; attachments go through evidence uploads and the scanner as write-once versions (channel `confirmation_response`), never parsed with formulas evaluated (ADR-052).
- **What the family never returns:** another confirmation, the engagement, any client portal link or grant, the firm's staff, or any field of the client's record beyond the one confirmation's render data. A client principal reaching any confirmation route gets 404.

## Revisit when
A third unauthenticated route is proposed, or branding needs per-visitor data.

## Related
- ADRs: amends ADR-013's clause "Pydantic models are the single source of truth..." only by adding two routes outside `AbacusRouter`; operates the ROUTE-001 rule.
- Plan: P-45; DEC-59; Q-01-T10, Q-01-T16, Q-01-T24.
- Specs: none.
