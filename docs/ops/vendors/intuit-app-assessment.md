# Intuit app assessment: draft answers (F-09-T05, F-09-T11 Intuit part; TASK-3099, DEC-2099)

Draft answers for Intuit's **App assessment questionnaire** (Production Settings in the developer
portal), drawn from the code on `main`. Ayush submits them; F-09-T12 checks them against the plan
of record before submission, and no answer may promise a control, region or certification we do
not hold on the day it is sent. Items marked **[open]** wait on another row; nothing here is a
commitment until submitted.

The app that goes to the assessment is a **new app with only `com.intuit.quickbooks.accounting`**.
The Quick Start app (payments and OpenID scopes saved) stays a sandbox-only throwaway: scopes
can't be removed once saved.

## App details

| Field | Answer |
|---|---|
| App name shown on Intuit's consent screen | **abacus** (Ayush, 2026-11-03; DEC-2099). A neutral name, so a firm's white-label portal never shows "Accrued" (DEC-01, ADR-133). This is the one place the code namespace is shown to clients, by Ayush's decision |
| Scope | `com.intuit.quickbooks.accounting` only. No Payments, no OpenID, no write scope (a write scope waits on the W1 adapter ADR) |
| Host domain | **[open: F-09-T09]** the neutral portal domain |
| Launch URL | **[open: F-09-T09]** `https://<connect host>/` (the firm app's connections screen) |
| Connect / reconnect URL | **[open: F-09-T09]** the same; clients start the connection from their portal |
| Disconnect URL | **[open: F-09-T09]** `https://<connect host>/` (disconnect is a button in the app, which revokes the grant at Intuit) |
| Redirect URI (production) | **[open: F-09-T09]** `https://<connect host on the neutral portal domain>/v1/connections/callback`, never a firm's white-label host (live-ledger cutover runbook, step 2) |
| Privacy policy URL | **[open: counsel, F-09-T04 rows]** a public page |
| End-user licence agreement (EULA) URL | **[open: counsel, F-09-T04 rows]** a public page |

## Compliance

| Question | Draft answer |
|---|---|
| Who uses the app | US accounting, audit, tax and client-accounting firms. Their clients connect their own QuickBooks Online company so the firm can read its trial balance |
| What data is read | The TrialBalance report for a chosen period, plus CompanyInfo as a daily connection health check. Nothing else |
| Do you write to QuickBooks | No. The connector sends only GET requests to the accounting API. The only POSTs are to Intuit's token and revoke endpoints. The egress client refuses every other POST before it leaves the process (`kernel/egress.py`; ADR-040), and a test intercepts and checks every request the connector sends (`tests/unit/connections/test_qbo_connector.py`) |
| Regulated industry | Accounting and tax services. Firms handle tax return information under IRC section 7216 and their own professional standards. We do not move money and are not a payments, lending or credit app |
| Hosting | AWS, region us-east-2 (production). Disaster recovery in us-west-2 **[confirm against the DR plan on the day]** |
| Encryption in transit | TLS 1.2 or higher on every public endpoint. Outbound calls to Intuit are HTTPS only; no redirect following; no proxies taken from the environment |
| Encryption at rest | Database storage encrypted with AWS KMS. QuickBooks tokens are additionally sealed with the firm's own key before storage, and erased when the client disconnects |
| Token storage | Access and refresh tokens are stored only sealed (encrypted) server-side, never in a browser, never logged |
| Access control | Firm staff sign in through WorkOS with MFA. Every permission check goes through one authorisation layer. Every database query is scoped to the firm by PostgreSQL row-level security |
| Audit | Connect, disconnect, token rotation, grant revocation and each sync run are recorded in an append-only audit trail |
| Data retention | Pulled trial balances become immutable ledger snapshots kept under the firm's engagement retention policy. On disconnect, the tokens are revoked at Intuit and erased; snapshots already taken stay with the engagement as audit evidence **[counsel to confirm wording for the privacy policy]** |
| Certifications | No SOC 2 report yet **[state the planned date only if the plan of record holds one on the day]**. No third-party penetration test yet (deferred, DEC-1389) |
| Incident contact | **[open: Ayush]** a monitored company address |

## Technical questions

| Intuit's question | Answer | Evidence |
|---|---|---|
| OAuth 2.0 authorisation-code flow | Yes, with PKCE (S256) | `connectors/quickbooks_online.py` `authorise_url`, `exchange_code` |
| `state` parameter checked against CSRF | Yes. The state is random, single-use, unexpired and this person's, and carries the sealed PKCE verifier; anything else is refused and audited | `connections/connect.py` (A-02-T16, DEC-515 L6) |
| Uses Intuit's discovery document | Yes. Authorisation, token and revoke endpoints are read from `developer.intuit.com/.well-known/openid_configuration` (sandbox: `openid_sandbox_configuration`) once a day per environment, with pinned fallbacks restricted to Intuit HTTPS hosts | `_endpoints` (DEC-2099) |
| Refreshes the access token only when it expires | Yes. A refresh runs only when the access token has under 5 minutes left. The rotated refresh token replaces the stored one in one transaction | `refresh`, `_EARLY_REFRESH` |
| Handles an expired or revoked refresh token (`invalid_grant`) | Yes. The connection is marked "needs reconnect" and the client is asked to reconnect; no retry loop | `refresh`, C20 reauth reason |
| Retries a failed authorisation automatically | No | — |
| Handles 401 on API calls | Yes. Treated as an expired token; the client is asked to reconnect | `_get` |
| Handles 429 and 5xx | Yes. Treated as provider unavailable; the sync activity is retryable, so the workflow's retry policy (Temporal, exponential backoff) tries again | `_get`, `connections/activities.py` |
| Captures `intuit_tid` | Yes. Logged with the endpoint and status for every response; no tokens, bodies or company data in the log | `_call` (DEC-2099) |
| Revokes tokens on disconnect | Yes. Disconnect revokes the refresh token at Intuit's revoke endpoint, then erases it | `revoke`, DEC-515 M1 |
| Uses the OAuth Playground for production tokens | No | — |
| Uses Change Data Capture (CDC) or webhooks | No. Reads are on demand for a period | `changes_since` raises `NotSupported` |
| Minor version pinned | Yes, `minorversion=75` | `MINOR_VERSION` |
| Sandbox tested end to end | Yes, 2026-11-03: connect, company info, trial balance (47 rows), forced refresh with rotation | `python -m abacus_tools.qbo_sandbox` (PR #1113) |

## After submission

Record in `docs/ops/vendors/README.md` the submission date and Intuit's ticket number (the
row's "dated ticket"), with QBO CSV and GL import as the fallback. Intuit's follow-up questions
are F-09-T28; the production-keys follow-ups are F-09-T64 and F-09-T81. Intuit's security review
follows the technical one. Critical, high and medium findings must be fixed within 2 weeks of
notice.
