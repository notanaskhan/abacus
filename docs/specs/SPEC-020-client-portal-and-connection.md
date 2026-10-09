---
id: SPEC-020
title: Client portal, connection and uploads
status: draft
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-011, ADR-016, ADR-030, ADR-035, ADR-037, ADR-040, ADR-052]
related_specs: [SPEC-000, SPEC-015, SPEC-016]
created: 2026-10-09
updated: 2026-10-09
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
This is Phase 2 increment 2, built on the connector contract (ADR-037) so that it works now with the fake connector and takes the first real ledger later without changing the flow:
- **Client portal:** a client user opens an engagement and sees its client-visible request items (contributors see only the items assigned to them), with status.
- **Connection flow:** a client admin connects the engagement's client entity to its ledger. They pick a provider, read the consent copy (ADR-040), authorise with the provider, and return to an active connection.
- **Access log:** every pull (sync run) is visible to the client admin and to the engagement partner and manager.
- **Connection health:** status, last successful pull, and an on-demand health check, shown to both sides.
- **Revoke:** a client admin, engagement partner or manager ends a connection; pulls stop at once.
- **Manual upload (founder, 2026-10-09):** a client can upload files for a request item instead of, or as well as, a pull. Each upload becomes a new evidence version (ADR-004) with upload provenance. This brings forward the upload part of increment 6; matching and screening stay there.

## 2. Problem and context
- **The pieces exist but nothing joins them:** retrieval runs end to end (SPEC-000) through `connections`, but a connection can only be created by seed scripts. Client users can sign in (SPEC-015), but the portal only lists their firms (SPEC-016).
- **The matrix already has the actions:** `connection.create` (client admin only), `connection.revoke` and `connection.read_log`.
- **The first ledger isn't chosen yet** (Phase 0), so this spec ships with the fake connector as the only provider outside production (Q1).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Client admins | View items; upload to any client-visible item; connect, check and revoke the ledger connection; read the access log |
| Client contributors | View their assigned items; upload to them |
| Engagement partners and managers | See connection health and the access log; revoke |

## 4. Goals and non-goals
**Goals**
- **Client engagement page** (`/client/engagements/$id`):
  - the engagement's name, the firm's name and the fiscal period;
  - request items grouped by audit area, with status and due date where set, read-only;
  - a Connection panel for client admins.
- **Connecting:**
  - `GET /v1/engagements/{id}/connection/providers` lists providers available in this environment, with their capabilities;
  - `POST /v1/engagements/{id}/connection/start` (`connection.create`, fresh MFA) takes a provider, stores a single-use `state` bound to the user, engagement and client entity (10-minute expiry), and returns the provider's authorise URL;
  - `GET /v1/connections/callback` checks the state, calls `exchange_code`, seals any tokens with the tenant's key (ADR-035), creates the connection as `active` with its scopes, audits `connection.created`, and redirects to the client engagement page;
  - one active connection per client entity: connecting again replaces the old one, which is revoked in the same unit of work (Q3).
- **Consent copy (ADR-040):** before authorising, the client sees per-provider copy stating that the platform is technically restricted to reading, logs every access in a log they can see, and can be disconnected at any time. It never claims the provider's token is read-only unless the provider grants a read-only scope (Q2).
- **Health:** `GET /v1/engagements/{id}/connection` returns provider, status, scopes, connected by and at, expiry, and the last successful pull. `POST …/connection/check` runs `health()` and records the result; a failed check marks the connection `needs_attention`.
- **Access log:** `GET /v1/engagements/{id}/connection/log` (`connection.read_log`) lists sync runs newest first (dataset, period, status, when, who started it), paginated.
- **Revoke:** `POST /v1/engagements/{id}/connection/revoke` (`connection.revoke`, confirmed in the UI) sets the connection `revoked`, deletes its sealed tokens, audits `connection.revoked`, and notifies the other side (`connection.revoked` kind).
- **Firm side:** the engagement Overview gains a Connection card (health, last pull, revoke, a link to the access log).
- **Manual upload:**
  - `POST /v1/engagements/{id}/request-items/{item_id}/uploads` (`evidence.upload`; contributors only on assigned items) takes the raw file body with its file name and media type (no multipart, as SPEC-008 D3);
  - checks: size up to 25 MB; type from an allowlist (PDF, Excel, Word, CSV, PNG, JPEG) checked by the file's leading bytes, not the name or header; the item is open or received and client-visible (Q6);
  - stores the bytes in the evidence store (Object Lock, ADR-016) and adds an evidence version with provenance `client_upload` (uploader, file name as untrusted text, size, SHA-256); the item becomes `received`; audit `evidence.uploaded`; the firm's assignees are notified (`evidence.uploaded` kind);
  - the same file (same hash) on the same item twice is refused as a duplicate;
  - on each item in the portal: "Upload files" (several files, one request each, with progress), and the item's upload history (file name, who, when) visible to the client;
  - firm side: uploaded versions appear on the Board and in the review queue as other evidence does.

**Non-goals**
- A real ledger connector (increment 3 and the Phase 0 choice).
- Retrieval scheduling or change detection (increment 9).
- Matching uploads to items automatically, email reply matching and screening (increment 6).
- Previewing or rendering uploaded files in the browser.
- Firm branding beyond the firm's name (Q4).

## 5. User stories and acceptance criteria
- **AC-1** Given a client admin or contributor, when they open an engagement in the portal, then they see its client-visible request items (contributors only their assigned ones) grouped by area with status, and nothing from another engagement or firm.
- **AC-2** Given a client admin, when they connect, then they see the provider's consent copy first, are sent to the provider's authorise URL with a single-use state, and on return have an active connection; a reused, expired or mismatched state is refused and nothing is created.
- **AC-3** Given anyone other than a client admin of that engagement, then starting a connection is refused (403), and the start requires fresh MFA.
- **AC-4** Given a connection, then the client admin, engagement partner and manager see its health and last successful pull, and a health check updates it; a failed check shows "needs attention".
- **AC-5** Given pulls have run, then the access log lists every sync run with dataset, period, status and time, to the client admin, engagement partner and manager only.
- **AC-6** Given a revoke, then the connection stops at once (a new retrieval fails `no_connection`), its tokens are destroyed, the action is audited, and the other side is notified.
- **AC-8** Given a client admin, or a contributor on an assigned item, when they upload an allowed file, then a new evidence version is stored with upload provenance, the item shows received, the firm is notified, and the upload is audited. A contributor uploading to an unassigned item is refused (403).
- **AC-9** Given a file over 25 MB, of a type not on the allowlist (judged by its contents), or already uploaded to that item, then it is refused with a plain message and nothing is stored.
- **AC-7** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Behaviour and flows
1. Client admin opens the engagement, chooses Connect, picks a provider, reads the consent copy, and confirms.
2. The SPA calls `start`; a 403 opens "Confirm it's you".
3. The browser goes to the authorise URL. The fake connector's URL points straight back to the callback with a code (local and test only).
4. The callback completes and redirects to `/client/engagements/$id?connected=1`.
5. Retrievals started by the firm (existing route) now find the active connection.

## 7. Domain and data changes
One migration in `connections` (protected):
- `connection_states` (id, tenant, engagement, client entity, user, provider, state hash, expires_at, used_at);
- `connection_secrets` (connection id, sealed token bytes, key version), deleted on revoke;
- `connections.status` gains `needs_attention` and `revoked`; columns `last_checked_at` and `last_check_ok`.

All tenant-scoped with forced RLS. Uploads need no schema change if evidence versions already carry a provenance kind; otherwise one evidence migration adds `client_upload` (protected).

## 8. Interfaces
The routes in §4. The callback is the only route without a tenant header; it resolves the tenant from the state row through a definer function.

## 9. Authorisation and tenancy
Matrix actions only (no new rows): `connection.create`, `connection.revoke`, `connection.read_log`, and `request_item.read` for the portal. The callback acts only as the user who started the flow, checked against the state row.

## 10. AI behaviour
None.

## 11. Integrations
The connector contract only. The fake connector serves locally and in tests; production lists no provider until the first real connector ships.

## 12. Edge cases and failure modes
- **The provider returns an error or the user cancels:** the callback shows "Not connected" with the provider's error code only, and the state is spent.
- **Two admins connect at once:** the later callback wins; the earlier connection is revoked (Q3).
- **Token expiry:** `refresh` is attempted on health check; failure sets `needs_attention`.
- **Revoked while a retrieval runs:** the running stage fails `connection_revoked` on its next call.

## 13. Security and privacy
- **State:** random, single-use, short-lived, stored hashed, bound to the user.
- **Tokens:** sealed with the tenant's key, never logged, never returned by any route.
- **Redirects:** to the fixed portal path only (no open redirect).
- **Client content stays hostile:** provider error text is never shown or logged; only codes.

## 14. Audit trail and evidence integrity
`connection.started`, `connection.created`, `connection.checked`, `connection.revoked`, each with the connection or state id and provider.

## 15. Observability
Counts of starts, completions, failures by code, and health check results.

## 16. Performance and scale
One connection per client entity; log pages of 50.

## 17. UX
The SPEC-016 client portal shell. The consent step is a dialog with the provider's copy and an explicit "Connect" button. The firm Overview Connection card follows the Panel pattern.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-3, AC-5 | integration | Visibility and refusals by role, across engagements and tenants |
| AC-2 | integration | Full flow with the fake connector; reused, expired and mismatched states refused |
| AC-4, AC-6 | integration | Health check and revoke; retrieval after revoke fails `no_connection` |
| AC-8, AC-9 | integration | Upload by role and assignment; size, type-by-content and duplicate refusals; nothing stored on refusal |
| AC-1 to AC-9 | component (vitest) | Portal page, consent dialog, connection panel, firm card |

## 19. Rollout
One migration. No flag: there's no provider in production until increment 3.

## 20. Open questions
- [ ] **Q1: providers before the ledger is chosen.** *Recommendation:* list only the fake connector ("Demo ledger"), and only in local and test; production shows "No ledger available yet". The first real connector is increment 3.
- [ ] **Q2: consent copy.** *Recommendation:* a fixed generic text now, reviewed by you; per-provider text added with each real connector (ADR-040 requires review per provider).
- [ ] **Q3: reconnecting.** *Recommendation:* one active connection per client entity; a new connection revokes the old one in the same unit of work.
- [ ] **Q4: branding.** *Recommendation:* firm name only for now; logos need file upload and are deferred.
- [ ] **Q5: protected path.** `connections` is protected, so the task needs your approval file. *Recommendation:* yes, covering `backend/src/abacus/modules/connections/**`, its migration and `backend/tests/unit/**`.

- [ ] **Q6: who can upload.** *Recommendation:* clients only in this spec, as the matrix allows (admins on any client-visible item, contributors on assigned items). Firm staff uploading on a client's behalf comes with increment 6.
- [ ] **Q7: malware scanning.** No scanner is in the dependency allowlist. *Recommendation:* the type allowlist by content and size limit now; files are stored and never rendered or opened by the platform. Scanning (S3 malware protection) is added with the staging deploy (TASK-014), before any real client data.
- [ ] **Q8: protected paths for uploads.** *Recommendation:* the approval file also covers `backend/src/abacus/modules/evidence/**`.

## 21. Future / explicitly deferred
- Real ledger connectors and their consent copy.
- Firm logos on the portal and invitations.
- Scheduled syncs (increment 9).
- Malware scanning (with TASK-014) and in-browser previews.
