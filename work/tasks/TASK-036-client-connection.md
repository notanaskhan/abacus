---
id: TASK-036
title: Client connection flow, health, access log and revoke
spec: SPEC-020
acceptance_criteria: [AC-2, AC-3, AC-4, AC-5, AC-6, AC-7]
risk_zone: red
status: done
branch: task-036-client-connection
worktree:
created: 2026-10-09
updated: 2026-10-09
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement the connection half of SPEC-020 (TASK-035 D1 split): a client admin connects the engagement's client entity through the connector contract, and both sides see health and the access log and can revoke.

## Scope
SPEC-020 §4 "Connecting", "Consent copy", "Health", "Access log", "Revoke", "Firm side"; AC-2 to AC-7.

## Context to load
- Spec: `docs/specs/SPEC-020-client-portal-and-connection.md`; ADR-035, ADR-037, ADR-040
- Code: `connections` (connector contract, fake connector, repository, pipeline `pull_raw`), `kernel.crypto` (`seal`, `open_sealed`), `kernel.config` (`fake_connector_dir`, environment), migration 0009, the notifications catalogue, `apps/web` `ClientEngagement` and `Overview`

## Plan
- [x] Plan approved by human (founder, 2026-10-09: D1–D7). Approved by founder: paths listed under *Protected paths*

### What the code shows
- **Connections can't be created by the app:** the provider is limited to `'fake'`, status to `active` or `revoked`, and the app may only update `status`.
- **The fake connector refuses OAuth:** `authorise_url` and `exchange_code` raise `NotSupported`.
- **The contract can't hand back tokens:** `exchange_code` returns nothing, so there's nowhere to put credentials.
- **The matrix has no fresh-MFA rule on `connection.create`** (SPEC-020 AC-3 asks for one), and no action for a health check.
- **Revoking mid-retrieval already works:** `pull_raw` refuses any connection that isn't `active` (`connection_inactive`).

### Design (for founder review)
1. **The callback lands in the SPA, not the API (D1).**
   - The provider redirects to `/client/connect/callback?state=…&code=…`. That page posts both to `POST /v1/connections/complete` with the client's own bearer token and tenant.
   - The API then needs no unauthenticated route and no definer function to find the tenant (SPEC-020 §8 assumed both). The flow is bound to the user who started it twice: by the session and by the state row.
2. **The contract (D2):**
   - `exchange_code` returns `Credentials | None` (opaque bytes);
   - connector factories receive the opened credentials;
   - the fake connector gets a demo OAuth: its authorise URL is the redirect URI with `code=demo` and the state, it accepts only `demo`, and it returns a fixed demo credential, so sealing and deletion are exercised.

   This is the only contract change, and it happens before the contract freezes (after increment 4).
3. **Data (migration 0029, connections):**
   - `connection_states`: id, tenant, engagement, client entity, user, provider, `state_hash` (SHA-256), `expires_at` (+10 minutes), `used_at`. Forced RLS. The app may insert, and update `used_at` only.
   - `connection_secrets`: connection id (primary key), sealed bytes, `key_id`. Forced RLS. The app may insert and delete; there are no updates.
   - `connections`:
     - `status` gains `needs_attention`;
     - new columns `last_checked_at`, `last_check_ok`, `revoked_at`, `revoked_by`;
     - the app may now insert, and update those columns;
     - a partial unique index allows one live connection (`active` or `needs_attention`) per client entity (Q3);
     - the provider check is unchanged (`'fake'`).
4. **Service (connections):**
   - `providers(ctx, engagement)`: `fake` ("Demo ledger") only when `fake_connector_dir` is set (local, test and evaluations), else empty (Q1).
   - `start(ctx, engagement, provider)`:
     - authorises `connection.create` (fresh MFA, D3);
     - stores the hashed state;
     - audits `connection.started`;
     - returns the authorise URL and the consent copy's version.
   - `complete(ctx, state, code)`, in one unit of work:
     - finds the state by hash for this user and tenant, unused and unexpired, and marks it used whatever the outcome;
     - authorises `connection.create` again;
     - calls `exchange_code`, seals any credentials with the tenant's key (`seal`, the connection ID as the fingerprint);
     - revokes any live connection for the entity (audited);
     - inserts the new one as `active` and audits `connection.created`.

     A provider error refuses with its code only (`connection_failed`); provider text is never kept.
   - `check(ctx, engagement)` (`connection.check`, D4):
     - runs `refresh` then `health`;
     - records `last_checked_at` and `last_check_ok`;
     - `active` becomes `needs_attention` on failure, and back on success;
     - audits `connection.checked`.
   - `revoke(ctx, engagement)` (`connection.revoke`):
     - status becomes `revoked`, with `revoked_at` and `revoked_by`;
     - deletes the secret and audits `connection.revoked`;
     - emits `ConnectionRevoked`, which notifies the engagement's partner and managers when a client revoked (D5).
   - `connection_of(ctx, engagement)` (`connection.read_log`) and `access_log(ctx, engagement, page)`: the sync runs of the engagement, newest first, 50 a page, filtered with `visible()`.
5. **Routes:**
   - `GET /v1/engagements/{id}/connection/providers`
   - `POST …/connection/start`
   - `POST /v1/connections/complete`
   - `GET …/connection`
   - `POST …/connection/check`
   - `POST …/connection/revoke`
   - `GET …/connection/log`
6. **Web:**
   - **Portal:** a Connection panel on the client engagement page (client admins only), with a provider picker and a consent dialog that shows the fixed generic copy (Q2), wording below. It also has the "Confirm it's you" prompt, health with "Check now", the access log, and Revoke with confirmation.
   - **Callback:** a `/client/connect/callback` page that completes the flow and returns to the engagement, or shows "Not connected" with a plain reason.
   - **Firm Overview:** a Connection card (status, last pull, check, revoke, access log).

**Consent copy (for your review, Q2):**

> **Connect your accounting system**
>
> Your auditor at {firm} will be able to retrieve the records they request for this audit, such as your trial balance, directly from your accounting system.
>
> - Abacus is built to only read from your system. It has no way to create, change or delete anything in it.
> - Every retrieval is recorded in an access log that you can see on this page at any time.
> - You can disconnect at any time. Retrieval stops straight away.
>
> On the next screen your accounting system will ask you to approve access. The permission it asks for may be broader than reading. Abacus still only reads.

**Protected paths (approval file):**
- `backend/src/abacus/modules/connections/**`;
- `backend/tests/unit/**`;
- `docs/architecture/permission-matrix.yaml` (D3, D4);
- `backend/src/abacus_tools/quality/schema_check.py` (new tables, grants and update columns);
- `backend/src/abacus_tools/quality/banned_patterns.py` (only if a lookup needs a LIST-001 exemption);
- `backend/src/abacus/api/app.py` (registering the two new routers; added by the founder on 2026-10-09).

### Questions for approval
- **D1. The provider redirects to the SPA, which completes the flow with the user's own token, rather than an unauthenticated API callback with a definer function?** *Recommendation: yes.* There's less attack surface and the flow stays bound to the user. This replaces SPEC-020 §8's callback wording.
- **D2. Change the connector contract so `exchange_code` returns opaque credentials, and give the fake connector a demo OAuth?** *Recommendation: yes.* Otherwise there's nowhere to keep a real provider's tokens, and the flow can't be exercised end to end.
- **D3. Add `mfa_recent: required` to `connection.create` in the matrix (SPEC-020 AC-3)?** *Recommendation: yes.*
- **D4. Add a matrix action `connection.check` for client admins, engagement partners and managers, and read the connection and log with the existing `connection.read_log`?** *Recommendation: yes.*
- **D5. Notify the engagement's partner and managers when a connection is created or revoked, but not client users (the catalogue never notifies them; they see the status on their page)?** *Recommendation: yes.*
- **D6. Approve the consent copy above?** *Recommendation: yes.* It's generic for now, reviewed per provider later (ADR-040).
- **D7. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [x] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] Every query is tenant-scoped; every endpoint checks authorisation
- [x] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Implemented:
  - migration 0029 (connection states, sealed secrets, health and revocation columns, one live connection per entity);
  - the contract change (`Credentials`) and the fake connector's demo sign-in;
  - start, complete, check, revoke, the connection and the access log, with routes;
  - the matrix's fresh MFA on `connection.create` and the new `connection.check`;
  - leads notified of connections and revocations;
  - the portal's Connection panel (consent, MFA prompt, health, log, disconnect), the SPA callback page and the firm Overview's card.

  Tests and checks:
  - backend unit 8,963 and web 146 passed; the gates pass; migration 0029 applies, rolls back and reapplies; the schema check passes;
  - a local end-to-end smoke against Postgres passed: providers, MFA refusal, start, complete, state reuse refused, credentials sealed and opened, check, reconnect replacing, revoke deleting the secrets, second revoke refused. The smoke data was removed afterwards.
  - The secrets table has no `key_id` column: the sealed envelope already carries its key ID.

  `api/app.py` was added to the approval by the founder (registering the routers). The TASK-034 slip on the same file is recorded there.
- `2026-10-09` — Design written for founder review after TASK-035 merged (#66).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The SPA completes the OAuth callback (D1) | No unauthenticated route; user-bound | No (SPEC-020 §8 amended) |

## Handoff
