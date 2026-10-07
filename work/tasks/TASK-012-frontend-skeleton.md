---
id: TASK-012
title: Sign-in, engagements and evidence board screens
spec: SPEC-000
acceptance_criteria: [AC-18]
risk_zone: amber
status: done
branch: task-012-screens
worktree:
created: 2026-10-06
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
React SPA screens: sign-in redirect, engagement list and creation, evidence board; generated client; design-system defaults; empty, loading and error states; sanitised agent text; one Playwright journey.

## Scope
In:
- three screens (SPEC-000 §17): sign-in redirect, engagement list and creation, and the evidence board for one engagement;
- the read routes the board needs (AC-18);
- a browser sign-in against a local fake OpenID Connect provider (§20);
- the generated client with TanStack Query;
- `packages/ui` on design-system defaults;
- the sanitised agent-text component (ADR-065);
- frontend unit tests and one Playwright journey with axe checks;
- `docs/architecture/reference/frontend-feature.md` (§22);
- fixing `make dev`.

Out: the client portal, a connections UI, SSO administration, styling beyond defaults, WorkOS (TASK-014), and refresh tokens (re-sign-in on expiry).

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-011, ADR-013, ADR-065, ADR-077, ADR-083, ADR-030, ADR-101
- `.claude/skills/frontend-feature/SKILL.md`

## Plan
- [x] Plan approved by human (founder, 2026-10-07: all recommendations, Q1–Q5)

### Design (for founder review)
Amber overall. The read routes touch red-zone modules (requests, evidence, agents, `abacus.api`), so those diffs get a red line-by-line review, independent tests and both reviewers.

**1. Read routes for the board (AC-18).** The board needs, for each request item, its evidence source (`Retrieved`), its status and its screening result. No route returns evidence or screening today. Module boundaries allow requests → (identity, engagements) and agents → (…, evidence, requests); nothing may read all three. Recommend (Q1) three reads that the SPA joins on `evidence_version_id`:
- `GET /v1/engagements/{id}/request-items` (exists; `request_item.read`) gains `evidence_version_id | null`: the item's latest fulfilment, which requests owns.
- `GET /v1/engagements/{id}/evidence-versions` (new, evidence; `evidence.read`) returns `{id, evidence_item_id, version_no, method (retrieved|uploaded), pulled_at, period}` for the engagement, through `visible()`.
- `GET /v1/engagements/{id}/screening-results` (new, agents; `evidence.read`, since a screening result is about evidence) returns the latest result per evidence version: `{evidence_version_id, action, confidence, rationale, citations (with verified/reason), unverified, created_at}`, through `visible()`.

All three are tenant-scoped, authorised, listed with `visible()` (LIST-001), and in the OpenAPI. The client is regenerated.

**2. Sign-in (§20, AC-1).** There is no browser flow today; `FakeIdentityProvider` is in-process only. Recommend (Q2):
- **Fake OIDC provider:** `abacus_tools/fakes/oidc_server.py`, local only, refusing other environments. It serves discovery, `/authorize` (a page listing the seeded dev users; click to sign in), `/token` (authorization code + PKCE, issuing an RS256 access token, 10-minute expiry) and `/jwks`, with the same issuer and audience as the API verifier.
- **SPA:** does authorization-code + PKCE itself with Web Crypto (no OIDC library is on the allowlist). The access token is kept in memory and `sessionStorage`. A 401 sends the user back through `/authorize`; there are no refresh tokens (ADR-030 allows short-lived tokens; WorkOS replaces this in TASK-014).
- **Tenant:** sent as `X-Abacus-Tenant` only when `/v1/me` reports several memberships; a firm picker in that case.
- **Seeding:** `make seed` runs `abacus_tools.local.seed_dev`, creating a firm, two users (a partner and a staff member), a client entity and a fake connection with a trial-balance fixture, idempotently, so the journey can retrieve.

**3. Frontend structure (ADR-011, ADR-101).**
- `apps/web`: TanStack Router (code-based routes, not the file-router plugin, so no extra dependency), TanStack Query, and the route tree `/signin/callback`, `/` (engagements), `/engagements/$id` (board). No business logic.
- `packages/api-client`: the hey-api `@tanstack/react-query` plugin, built into `@hey-api/openapi-ts`, generates `queryOptions`/`mutationOptions`. The client gets its base URL and auth/tenant headers from an interceptor set up in `apps/web`.
- `packages/ui`: shadcn-style primitives on Radix, cva, clsx, tailwind-merge and lucide: Button, Input, Label, Card, Table, Badge, Dialog, Alert, Skeleton, Spinner, EmptyState. Also `AgentText`.
- **Dev proxy:** Vite proxies `/v1` to the API, so the SPA is same-origin and needs no CORS.

**4. Screens.**
- **Engagements:** a list (name, client, period, status) and a create dialog. Empty state ("No engagements yet" plus create), loading skeleton, error alert with retry.
- **Board:** request items (description, audit area, status badge) with an add-item form and *Retrieve trial balance* (`POST …/retrievals`, polling the retrieval until it finishes).
  - Each item shows its evidence source (`Retrieved`) and version.
  - It shows the screening result: an action badge, confidence, the rationale through `AgentText`, citations with verified/unverified marks, and the unverified list.
  - It has empty, loading, partial (evidence but no screening yet: "Screening…") and error states.
  - Agent proposals are labelled as proposals; nothing in the UI accepts them (ADR-005).

**5. Agent text (ADR-065).** `AgentText` renders model text as React text only:
- it never uses `dangerouslySetInnerHTML`;
- it strips control and bidirectional-override characters;
- URLs aren't linkified;
- it caps the length.

ESLint bans `dangerouslySetInnerHTML` everywhere and bans `fetch`, `XMLHttpRequest` and axios outside `packages/api-client` (ADR-011). A custom rule allows the fields `rationale`, `quote` and `unverified` in JSX only as `AgentText` children. No sanitiser library is needed: text nodes can't carry markup.

**6. Tests (ADR-077, ADR-083).**
- **Unit:** Vitest + Testing Library for `AgentText` (hostile strings), the PKCE helpers, the states of both screens with a mocked client, and the board join.
- **Backend:** independent tests for the three reads (authorisation, `visible`, tenancy).
- **Journey:** one Playwright run — sign in (fake OIDC), create an engagement, add an item, retrieve, see the item `received` with source `Retrieved`, then the screening result appears (the worker with `FakeModel`), with axe checks on each screen. `make e2e` runs it locally; CI runs it nightly (stage 5, per ADR-083), not on PRs.

**7. `make dev` fix.** The current target points at missing entry points:
- run `uvicorn abacus.api.app:app`, `python -m abacus.worker`, the fake OIDC server and `pnpm dev`;
- add `make seed` and `make e2e`.

### Questions for approval
- **Q1. Board data:** three reads joined in the SPA (recommended; keeps module boundaries), or one composite `request-items` response (needs a new dependency edge or a read-model module)? If three reads, SPEC-000 §8's "List with evidence and screening" is met by the board, not by a single call.
- **Q2. Sign-in:** a fake OIDC server plus hand-rolled PKCE in the SPA (recommended; no new dependency), or ask to allowlist an OIDC client library now? Note that `@workos-inc/authkit-react` is pending for TASK-014.
- **Q3. Dependencies:**
  - Approve adding allowlisted packages: `@tanstack/react-router`, `@tanstack/react-query`, `tailwindcss`, `@radix-ui/*` (as needed), `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`; dev: `@testing-library/react`, `@playwright/test`, `@axe-core/playwright`.
  - Approve allowlisting `@tailwindcss/vite`: Tailwind v4's Vite plugin, which v4 needs (no PostCSS).
  - Approve allowlisting `@testing-library/dom`, a required peer of `@testing-library/react`.
  - Recommend not adding user-event or jest-dom.
- **Q4. Protected paths in the approval file:**
  - `apps/web/package.json`, `packages/ui/package.json`, `packages/api-client/package.json` and `openapi-ts.config.ts`;
  - `pnpm-lock.yaml`, `Makefile`, `docs/architecture/dependency-allowlist.yaml`;
  - `.github/workflows/` (nightly e2e);
  - `.claude/skills/frontend-feature/`;
  - backend: `abacus/api/**`, and `modules/requests/**`, `modules/evidence/**`, `modules/agents/**`;
  - `abacus_tools/fakes/**`, `abacus_tools/local/**`, `abacus_tools/quality/banned_patterns.py` (LIST-001 exemptions if needed), `backend/pyproject.toml` (if the OIDC server needs nothing new, unchanged).
- **Q5. Journey in CI:** nightly only (ADR-083 stage 5, recommended), or also on every PR (adds about 3–5 minutes plus the stack)?

### Interface contract — board reads (tests written independently — ADR-078)
All three reads:
- authenticate through `AbacusRouter`;
- check engagement membership (`get_ref` + `authorise`) before reading;
- are tenant-scoped (RLS) and filtered with `visible()`;
- return 404 for an engagement of another firm or an unknown one;
- return 403 for a firm member with no relationship to the engagement (and for anyone the matrix denies).

**`GET /v1/engagements/{engagement_id}/request-items`** (`request_item.read`; existing). `RequestItemOut` gains `evidence_version_id: UUID | null`:
- it is the version of the item's most recent fulfilment (by `created_at`, then `id`; the larger `id` wins a tie);
- it is null when the item has none;
- after a successful retrieval it equals the retrieval's `evidence_version_id`;
- other fields are unchanged.

**`GET /v1/engagements/{engagement_id}/evidence-versions`** (`evidence.read`; new; evidence module):
- returns `list[EvidenceVersionOut]`, oldest first: `{id, evidence_item_id, version_no, method ("retrieved"|"uploaded"), source, pulled_at, period_start, period_end, created_at}`;
- never content, storage keys or fingerprints;
- empty list when there are none;
- only this engagement's versions.

**`GET /v1/engagements/{engagement_id}/screening-results`** (`evidence.read`; new; agents module):
- returns `list[ScreeningResultOut]`, one per evidence version (the latest by `created_at`, then `id`; the larger `id` wins a tie);
- fields: `{id, evidence_version_id, action ("ready_for_review"|"needs_revision"), confidence (decimal string, 3 places), rationale, citations: [{cell, quote, value, verified, reason}], unverified: [str], created_at}`;
- only this engagement's results; empty when there are none;
- read-only: there is no route that acts on a result.

**Permissions.**
- `evidence.read` and `request_item.read` follow the matrix (engagement partner, manager, senior, staff, reviewer: allow).
- A `reviewer` may read all three.
- An archived engagement remains readable.
- Python names: `evidence.api.evidence_versions_for(ctx, engagement_id)`, `EvidenceVersionSummary`; `agents.api.screening_results_for(ctx, engagement_id)`, `ScreeningResultView`; repository list functions `evidence.repository.list_versions` and `agents.repository.latest_results` (LIST-001: `visible` in `.where`).

**OpenAPI and client.** The operations are `list_evidence_versions` and `list_screening_results`. `packages/api-client` is regenerated: `make check`'s drift check passes, and `test_openapi` matches.

### Interface contract — SPA, sign-in and journey (tests written independently — ADR-078)
**Local sign-in** (`backend/src/abacus_tools/fakes/oidc_server.py`; Python tests):
- `create_app()` refuses environments other than local and test.
- **`GET /authorize`**:
  - requires `response_type=code`, `client_id=abacus-web`, a `redirect_uri` in `REDIRECT_URIS`, `code_challenge_method=S256`, a `code_challenge` and a `state`; anything else → 400 `invalid_request`;
  - lists `DEV_USERS`, with every value HTML-escaped.
- **`POST /authorize`** (form: `redirect_uri`, `state`, `code_challenge`, `subject`): an unknown subject or redirect → 400; otherwise a 303 to `redirect_uri?code=…&state=…`.
- **`POST /token`** (form): the code is single use, even when the exchange fails; it expires after 60 s; `redirect_uri` and `client_id` must match; S256 of `code_verifier` must equal the challenge; otherwise 400 `invalid_grant`.
  - Success returns `{access_token, token_type:"Bearer", expires_in:600}` with `Cache-Control: no-store`.
  - The token verifies with `JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=<GET /jwks>)` and has `sub` = the chosen subject.
- **CORS:** only the two SPA origins, for POST.
- **Discovery** names the endpoints.
- **The key** persists in `backend/.local/oidc-key.pem` (tests must use a temporary path, e.g. by monkeypatching `KEY_FILE`).

**Seeding** (`abacus_tools.local.seed_dev.seed(dsn, fixtures_dir)`; integration):
- idempotent; creates the Dev firm, the `dev-leader` (practice_leader) and `dev-staff` users with memberships;
- for each engagement of the firm, ensures one active fake connection for its client entity and writes a balanced trial-balance fixture for its fiscal period;
- returns the number of new connections;
- refuses outside local/test or without `fake_connector_dir`.

**SPA units** (Vitest + Testing Library, files in `apps/web/src/**/*.test.tsx`; import the UI through `@abacus/ui`):
- **`sanitiseAgentText`** removes C0/C1 controls except newline/tab, bidi overrides and isolates (U+202A–202E, U+2066–2069), zero-width characters and the BOM; normalises CRLF to LF; truncates to 2000 code points plus `…`.
- **`AgentText`** renders text, never HTML: `<img onerror>` stays visible text; there is no anchor for URLs.
- **`codeChallenge(v)`** is base64url(SHA-256(v)) with no padding (RFC 7636 test vector). **`randomString`** is URL-safe and at least 43 chars for 32 bytes.
- **Session:**
  - `signIn()` stores `{state, verifier, returnTo}` and navigates to `${AUTHORITY}/authorize` with S256 parameters.
  - `completeSignIn` fails (`SignInFailed`) on a missing or mismatched state, no pending request, or a non-OK or malformed token response; on success it stores the token with its expiry and returns `returnTo`. The pending request is removed either way.
  - `accessToken()` is null within 30 s of expiry.
  - `safeReturnTo` rejects `//evil`, absolute URLs and the callback path.
- **`boardRows`:**
  - joins on `evidence_version_id` to give `none`, `pending` or `result`;
  - `awaitingScreening` is true only while some row is pending;
  - `sourceLabel` gives "Retrieved" or "Uploaded";
  - `statusLabel` covers all four statuses;
  - `confidencePercent("0.900")` is "90%".
- **Screens** (mock the network through the generated client, e.g. `client.setConfig({ fetch })`, never real HTTP):
  - **Engagements:** loading (busy skeleton), empty ("No engagements yet" plus a create button), error (alert with Retry), and the list with links to the board. Create sends the five fields and refreshes the list.
  - **Board:**
    - the item shows status, source `Retrieved · version N` and the screening result;
    - the rationale goes through `AgentText`: a hostile rationale is shown as text;
    - citations are marked Verified or Unverified, and `unverified` notes are listed;
    - pending evidence shows "Screening…";
    - error and empty states;
    - *Retrieve trial balance* posts the engagement's fiscal period and is disabled while running;
    - nothing on the board accepts a proposal (no accept/approve control).
  - **Layout:** signed out → redirect to sign-in (the splash `App` shows); several firms and no active tenant → firm picker, whose choice is sent as `X-Abacus-Tenant`.
- **Lint rules** (`apps/web/eslint.config.js`; test with ESLint's API): `dangerouslySetInnerHTML`, `fetch`/`XMLHttpRequest` (except `src/auth/session.ts`), `axios`, and a `.rationale`/`.quote` rendered outside `AgentText` are all errors.

**Contract revision 1 (after the security and architecture reviews; supersedes earlier bullets where they differ)**
- **Board reads.** `GET …/screening-results` records one audit event, `screening_result.read`, targeting the engagement, when it returns at least one result (results quote evidence content, as `evidence_version.read` does). The other two reads still write nothing.
- **`sanitiseAgentText`:**
  - normalises to NFC and CRLF to LF;
  - also removes U+00AD, U+034F, U+061C, U+115F/U+1160, U+17B4/U+17B5, U+180B–U+180F, U+2028–U+202E, U+2060–U+206F, U+2800, U+3164, U+FE00–U+FE0F, U+FFA0, U+FFF9–U+FFFC, and the tag and variation characters U+E0000–U+E007F and U+E0100–U+E01EF;
  - collapses 3 or more consecutive newlines to 2;
  - then truncates as before.
  - `AgentText` uses classes (`whitespace-pre-line` for blocks, `overflow-wrap:anywhere`), not inline styles.
- **Board citations.** `cell` and `value` are rendered through `AgentText` too.
- **Polling.** Screening is polled for at most 2 minutes from mount. After that, a pending row shows "Screening hasn't finished." with a "Check again" button, which refetches.
- **Retrieve.** The button is disabled from the click until the run ends (no gap before the first poll). The board refreshes once, in an effect, when the run ends.
- **Session.**
  - `signIn()` is latched: concurrent calls start one redirect and write one pending request.
  - `completeSignIn` also stores `abacus.signedInAt`.
  - `handleUnauthorised(now)` removes the token. It returns `"rejected"` (no redirect) if the last sign-in was within 10 s; otherwise it calls `signIn()` and returns `"redirected"`. The API client's 401 handler calls it.
  - Queries don't retry 4xx errors (`shouldRetry` in `src/api.ts`).
- **Router.** The root route has a not-found page ("Page not found", with a link to engagements) and an error page ("Something went wrong", with Reload).
- **CSP.** Production builds (`vite build`) carry a CSP meta tag: `default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' <authority>; frame-ancestors 'none'; object-src 'none'; base-uri 'none'`. Dev builds have none.
- **ESLint.**
  - The HTML/agent-text `no-restricted-syntax` rules apply to `src/**`, excluding `*.test.*`.
  - Writing HTML through a `dangerouslySetInnerHTML` object property, `innerHTML`/`outerHTML` assignment, or `insertAdjacentHTML`/`createContextualFragment` is an error.
  - `packages/ui` has its own lint config (HTML ban, no `fetch`), tsconfig and Prettier, all run by `make check-fast`.
- **Sign-in server.**
  - `code_verifier` must match RFC 7636 (43–128 of `[A-Za-z0-9-._~]`), otherwise `invalid_grant`, still consuming the code.
  - Expired codes are purged.
  - The key file is created mode 0600.
- **`seed_dev`.** `main()` refuses a superuser DSN whose host isn't loopback.
- **Journey.**
  - The workflow seeds before the journey (users must exist to sign in).
  - The journey runs the seed again after creating its engagement, to connect it (as the contract's step 3 says).
  - On failure the Playwright report is uploaded.

**Playwright journey** (`apps/web/e2e/journey.spec.ts`, config `apps/web/playwright.config.ts`, base URL `http://localhost:5173`; assumes `make dev` and `make seed`):
1. Sign in as `dev-leader` and see the firm name.
2. Create an engagement.
3. Run `make seed` (or `uv run python -m abacus_tools.local.seed_dev` with `ABACUS_FAKE_CONNECTOR_DIR`) to connect its entity.
4. Add a request item and press *Retrieve trial balance*.
5. The card shows "Received", "Retrieved · version 1", then an "Agent proposes" result with verified citations (screening by the worker's fake model; allow about 90 s).

Run `@axe-core/playwright` on the engagements page and the board, with no serious or critical violations. `make e2e` runs it; CI runs it nightly (implementer-owned workflow).

### Steps
1. Approval file. Backend reads (red): contract, independent tests, reviews.
2. Fake OIDC server, `seed_dev`, the `make dev`/`seed`/`e2e` targets.
3. Client generation with the TanStack Query plugin; `packages/ui`; ESLint rules.
4. Screens and states; `AgentText`; unit tests.
5. The Playwright journey with axe; the nightly CI job; the `frontend-feature.md` reference and skill update.
6. Two reviews, `make check`, PR (amber, with red parts reviewed line by line).

## Definition of done
- [x] All listed ACs have passing tests that reference them
- [x] Type check passes
- [x] Lint and format pass
- [x] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [x] Security scan passes; no secrets committed
- [x] No new dependencies, or each one approved and listed below
- [x] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [x] Module README and relevant docs updated
- [x] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| uvicorn | >=0.40 (locked 0.54) | ASGI server for `make dev` and the local sign-in server (allowlisted) | founder (allowlist; uv.lock approval 2026-10-07) |
| @tanstack/react-router, @tanstack/react-query, tailwindcss, @radix-ui/react-{slot,dialog,label}, class-variance-authority, clsx, tailwind-merge, lucide-react | see lockfile | SPA stack (ADR-011; allowlisted) | founder (Q3) |
| @tailwindcss/vite, @testing-library/dom | see lockfile | Tailwind v4 Vite plugin; Testing Library peer | founder (Q3, allowlisted in this task) |
| @testing-library/react, @playwright/test, @axe-core/playwright | see lockfile | unit tests and the journey (allowlisted) | founder (Q3) |

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-07` — Plan drafted (§1–7, Q1–Q5) for founder review while PR #13 (TASK-011b) awaits review. Found that `make dev` points at missing entry points, and that no route returns evidence or screening for the board.
- `2026-10-07` — Approved with all recommendations:
  - Q1: three reads joined in the SPA;
  - Q2: fake OIDC with hand-rolled PKCE;
  - Q3: allowlisted packages added, plus `@tailwindcss/vite` and `@testing-library/dom` allowlisted;
  - Q4: the approval file was written at the founder's instruction;
  - Q5: the journey runs nightly.

- `2026-10-07` — Implementation progress:
  - **Board reads** (with independent tests, 56 passing).
  - **Local sign-in:** a fake OIDC server with PKCE, `seed_dev`, `uvicorn`. The `uv.lock` approval was extended at the founder's OK.
  - **`make dev`/`seed`/`e2e`:** fixed, with the API on :8001 because :8000 is in use locally.
  - **Frontend:** `packages/ui` with `AgentText`; generated TanStack Query client with declarations (`--noCheck`); ESLint rules; screens.
  - **Scaffold test:** `App.test.tsx` was kept; `App` is now the sign-in splash.
  - **Smoke:** the full AC-18 journey passes by hand in a real browser (Playwright script): sign in → create → seed → add item → retrieve → Received / Retrieved / Agent proposes, with verified citations.
- `2026-10-07` — The security review (no blockers) and the architecture review (blocker: tests missing) are fixed; see Contract revision 1.
  - Independent tests: 102 Vitest tests, 38 sign-in server tests, 11 seed tests, the board reads tests (now with the audited screening read), and the Playwright journey with axe.
  - They found 2 bugs, both fixed: the firm picker didn't advance, and the polling-cap message never appeared.
  - `make check-fast` passes, and the journey passes against the local stack.
## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| API on :8001 in `make dev` | :8000 is commonly taken locally | No |
| The client publishes declarations (`dist/`, `tsc --noCheck`) and consumers type-check against them | Generated sources fail `exactOptionalPropertyTypes`; this keeps the flag for app code | No |
| A local helper (`seed_dev`) connects engagements to the fake connector | No connections UI in SPEC-000; each engagement creates its own client entity | No |
| `App` is now the sign-in splash | Keeps the scaffold test (never delete a test) while giving `App` a role | No |

## Gotchas and discoveries
-

## Questions for the human
-

## Handoff
- **Current state:** Done. PR #14 merged (rebase) 2026-10-07 at the founder's instruction while its full CI was still red: the integration stage failed on test fixtures that relied on the local compose stack and on pins that predate 011b/012. A test author is fixing those on `task-012-screens-ci`; the fixes land on main separately. The approval file is deleted.
- **Exact next step:** none (TASK-013). Follow-ups: WorkOS, the CSP header and refresh tokens (TASK-014); screening run status on the board.
