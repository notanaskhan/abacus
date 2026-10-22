---
id: ADR-163
title: White-label portal - neutral portal domain, same-origin /v1, host as a branding hint only, per-firm branded email
status: accepted
date: 2026-10-23
deciders: notanaskhan, ayushkbhatia
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
The client portal is the firm's portal. A client of Brightwater Hale sees Brightwater Hale's mark, name, address and people, and never the word "Accrued" (DEC-01, ADR-133, AGENTS frontend rule 7). Nothing in the ADR set covers where the portal is served, how it finds its firm before anyone signs in, or whose name client email goes out under.

The plan's chapters disagreed on the host. Chapter 04 §1.3 inferred `<slug>.portal.accrued.app`; chapter 03 §12.2 wrote `<slug>.portal.<accrued-domain>`; chapter 06 §1.12 (D-OPS-10) used a neutral portal domain. Chapter 09 recorded this as conflict X-12. A portal URL containing "accrued" breaks the white label in the one place every client reads: the address bar and every email link. DEC-59 settled it (option b), and this ADR records that decision as proposal P-11.

Constraints that shape the rest:
- The SPA calls the API through the generated client with `baseUrl = window.location.origin` and a CSP of `connect-src 'self'` and `img-src 'self'` (chapter 04 §1.3–1.4). Cross-origin API calls would need CORS and third-party cookies, which the BFF session design (ADR-141) avoids.
- POR-01 must render the firm's branding before sign-in, so one read is unauthenticated. `AbacusRouter` refuses routes without a matrix action; unauthenticated routes live on the ROUTE-001 exception list (ADR P-45, proposed as ADR-152).
- Tenant isolation is the first rule (ADR-014). A request header the client controls (`Host`) cannot decide which tenant's data a request may read.
- Client email (sign-in codes, invitations, reminders, POR-20 templates) must arrive in the firm's name and must land in inboxes, which needs a verified sending domain with DKIM per firm (RK-52).

The plan's chapters call this ADR "ADR-203". That number is a plan alias; P-11 takes the next free number on `main`, ADR-163 (`docs/adr/backlog.md`).

## Decision
1. **Two builds on two origins.** One Vite project (ADR-011) builds the firm app (`index.html` → `dist/`) and the portal (`portal.html` → `dist/portal`, `vite build --mode portal`). The firm app is served at `app.<product-domain>`; the portal is never served on the firm app's origin, and the firm app is never served on a portal host or a custom domain. The portal bundle contains no firm-app chunk and no "Accrued" string.
2. **The portal's default host is `<slug>.<neutral-portal-domain>`.** The neutral portal domain is a registered domain that does not contain "accrued" (case-insensitive) in any label. It is a deployment setting (`portal_base_domain` in `runtime-config.json`), never a constant in code. The firm's slug is the leftmost label. Firm custom domains (`portal.<firm-domain>`, CNAME to the portal distribution, ADM-10 *Pending DNS → Verified*) come in P1 and are stored in `portal.portal_domains`; a custom domain is an additional host for the same firm, never a replacement for tenant resolution rules below.
3. **Portal routes sit at the origin root.** `/sign-in`, `/accept`, `/`, `/documents` and the rest have no `/client` prefix (chapter 04 §5.1, P-08 §5.1). The legacy `/client/*` subtree in the firm bundle is removed when the portal entry replaces it (P-08-T28).
4. **`/v1` is proxied same-origin on every host.** The CDN routes `/v1/*` on each portal host (default or custom) to the API. The portal keeps `connect-src 'self'`, needs no CORS, and uses no third-party cookie. Session cookies are `__Host-` cookies on the portal host (ADR-141's BFF pattern).
5. **The host is a branding hint only.** The API resolves `Host` to a firm only to choose branding, through the SECURITY DEFINER lookup `portal_resolve_host` over `portal_domains`. Authorisation never comes from the host: it comes from the session's membership and client access grants (ADR-002, ADR-146). A portal session is pinned to the tenant and host it was minted on; presented on another firm's host or on the firm app host it is answered exactly as no session (401 `unauthenticated`). A staff session presented on a portal host is refused the same way.
6. **One unauthenticated branding surface.** `GET /v1/portal/branding` returns Public-classified fields only (`firm_name`, `portal_name`, `logo_url`, `address_line`, `help_url`, `privacy_url`, `support_contact_name`, `secured_footer`, `sign_in {methods, mfa_floor}`, `maintenance_banner`). An unknown host gets the same shape with neutral values; no response carries a tenant identifier. The logo is re-encoded server-side and served same-origin at `GET /v1/portal/branding/logo` (CSP `img-src 'self'`). Both routes sit on the ROUTE-001 exception list that ADR P-45 (ADR-152) owns; ADR-152 lists `/v1/portal/branding` today and must add `/branding/logo` before it is accepted (P-08 OQ-2). Branding is cached at the edge keyed by host.
7. **Branding is slots, not theming.** A firm sets logo, portal name, address, help and privacy links, support contact and sender; the accent stays espresso and firms cannot override CSS variables (ADR-155). The "Secured by Accrued" footer is a firm setting that defaults to **off**; while it is off, nothing on the portal or in client email names Accrued.
8. **Branded email per firm.** Client email goes out through SES (COMM-001's single transport) in the firm's display name:
   - When the firm has verified its own domain (Easy DKIM, custom MAIL FROM `bounce.<firm-domain>`, DMARC guidance on ADM-10), mail is sent from that domain with DKIM signed for it. **Per-firm DKIM and the sender-domain lifecycle are R-01's** (ADM-10, POR-20), on Q-01's SES setup.
   - Until then, mail is sent from `<slug>@<neutral-mail-domain>` with the firm's display name and `Reply-To` the firm's address. The neutral mail domain, like the portal domain, never contains "accrued".
   - Templates are database content (C16, `communications.email_templates`); links in client email always point at the firm's verified portal host (custom domain when active, else the default host) and carry opaque tokens, never data in query strings.
9. **Platform-side mail is separate.** Firm-side system mail (staff invitations) uses the platform identity on `mail.<product-domain>`; it never reaches a client.

Solo-edition reading: "accepted by notanaskhan" in the plan is recorded as acceptance with both handles in `deciders` (`docs/plan/AMENDMENT-solo.md`); there was no meeting.

## Options considered
### Option A: neutral portal domain, same-origin `/v1`, host as branding hint - chosen
- Pros: the white label holds in the address bar and every email link; one wildcard certificate covers every firm's default host; same-origin keeps the CSP strict and avoids CORS; tenant isolation never depends on a header.
- Cons: a second registered domain (and a neutral mail domain) to buy, verify and keep reputable; the edge must route `/v1` per host.

### Option B: `<slug>.portal.accrued.app`
- Pros: one domain family; simpler DNS and certificates.
- Cons: every portal URL and email link says "accrued".
- Why rejected: breaks DEC-01/ADR-133 and the design's white-label rule (X-12, DEC-59).

### Option C: custom domains only
- Pros: the firm's own name in the URL.
- Cons: no portal until a firm's IT adds DNS records; design-partner onboarding would wait on partner IT.
- Why rejected: custom domains are P1; a default host is needed from M5.

### Option D: a separate API origin (`api.<domain>`) with CORS
- Pros: one API hostname.
- Cons: CORS on every call, a cross-site cookie for the BFF session, a looser `connect-src`; the API origin would name the vendor unless it too were per firm.
- Why rejected: conflicts with the BFF cookie design (ADR-141) and the CSP.

### Option E: resolve the tenant from the host for authorisation
- Pros: fewer lookups.
- Cons: a client-controlled header would choose the tenant.
- Why rejected: tenant comes from the session and grants only (ADR-014, ADR-146).

## Consequences
**Positive**
- A client never sees "Accrued" unless the firm turns the footer on.
- Branding before sign-in costs one cached, Public read; no tenant data is exposed to unknown hosts.
- Host pinning closes the cross-firm session replay path that pen test #1 will try (P-08-T25).

**Negative / costs accepted**
- Two extra domains (portal, mail) and their reputation to manage; F-09-T09 registers them.
- Until a firm verifies its own domain, mail comes from the neutral mail domain, which may land in spam more often (RK-52).
- `portal_resolve_host` is a SECURITY DEFINER function that must stay in `DEFINER_FUNCTIONS`.

**Follow-up work created**
- **Domains:** product, neutral portal and neutral mail domains registered (F-09-T09).
- **Edge:** CloudFront portal distribution with a wildcard certificate on the neutral portal domain, `/v1/*` same-origin to the internal ALB, WAF rate rules, `portal_base_domain` in `runtime-config.json`; custom domains as distribution tenants in P1 (Q-01, OPS-14; RB-21).
- **Branding and host resolution:** `portal_branding`, `portal_domains`, `portal_resolve_host`, the branding and logo routes, the logo re-encode service (P-08-T05).
- **Exception list:** ADR-152 (P-45) adds `/v1/portal/branding/logo` before acceptance (P-08 OQ-2).
- **Portal build:** `portal.html`, `entries/portal.tsx`, `vite --mode portal` with the portal CSP and the no-"Accrued" bundle check (P-08-T07).
- **Host pinning tests:** `test_portal_host_pinning.py` (P-08-T25).
- **Email:** sender-domain lifecycle with per-firm DKIM, custom MAIL FROM, DMARC guidance and POR-20 templates (R-01, ADM-10); SES identities and configuration set (Q-01); deliverability runbook RB-20.

## Enforcement
- [ ] Lint rule: the white-label lint (F-05-T39, L7) fails any portal namespace, email preview or portal bundle string containing "Accrued" while `secured_footer` is false.
- [ ] Test: `test_portal_host_pinning.py` proves a portal session presented on another firm's host or the firm app host gets 401 `unauthenticated`, and that `Host` changes branding only.
- [ ] Test: the branding contract test proves the payload holds Public fields only and that a known and an unknown host get the same shape (P-08-T05, T20).
- [ ] Test: a config check refuses a `portal_base_domain` or neutral mail domain containing "accrued".
- [ ] Architecture rule in CI: the portal build emits no firm chunk and no "Accrued" or fixture string (P-08-T07).
- [ ] Hook or protected path: ROUTE-001 exception list in `backend/src/abacus/api/app.py` (ADR-152); `DEFINER_FUNCTIONS` in `schema_check.py`.
- [ ] Reviewer agent checklist item: no authorisation decision reads `Host`; no hard-coded portal or mail domain.

## Guidance for agents
Treat the request host as a hint for which logo to show and nothing else. Every tenant decision on a portal request comes from the session's grants. Never write a product, portal or mail domain into code: read it from runtime config. In portal code and client email, use the firm's display name from branding.

**Do**
```
branding = await portal.api.branding_for_host(request.headers["host"])   # Public fields, neutral when unknown
ctx = await identity.api.portal_context(session)                         # tenant from the session, pinned to its host
```

**Don't**
```
tenant_id = TENANT_BY_HOST[request.headers["host"]]   # the host never decides the tenant
PORTAL_URL = f"https://{slug}.portal.accrued.app"     # never a domain constant; never "accrued" in a portal host
```

## Revisit when
WorkOS cannot hold a redirect URI per portal host and an `auth.<neutral-portal-domain>` hop is needed (chapter 06 §1.12); CloudFront multi-tenant limits or pricing force one distribution per custom domain; a firm asks for the portal on the firm app's domain; or the neutral domains' reputation fails the M10 deliverability gate.

## Related
- P-ID: P-11 (DEC-59; settles X-12), drafted by P-08-T30. Plan alias "ADR-203" maps to ADR-163 (`docs/adr/backlog.md`).
- ADRs: ADR-133 (product naming; the portal never shows Accrued), ADR-011 (React SPA; entry points), ADR-141 (P-54 authentication; portal BFF session), ADR-146 (P-09 client identity and grants), ADR-152 (P-45 unauthenticated routes, proposed), ADR-155 (design system; espresso locked), ADR-014 (RLS), ADR-002 (identity and memberships).
- Docs: `docs/plan/09-decisions-adrs.md` P-11, DEC-59, X-12; `docs/plan/03-backend-architecture.md` §12.2–12.3; `docs/plan/04-frontend-architecture.md` §1.3; `docs/plan/06-platform-ops-security.md` §1.11–1.12 (D-OPS-10, D-OPS-11); `docs/plan/epics/P-08.md` §0.1, §3.1, OQ-2; `docs/screens/POR-01.md`, `docs/screens/POR-02.md`.
