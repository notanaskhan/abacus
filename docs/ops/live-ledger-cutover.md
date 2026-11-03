# Live-ledger production cutover (A-02-T33; SPEC-333 AC-52; DEC-70, DEC-709)

QuickBooks Online is the first live ledger (read only, ADR-040). This is the cutover from the
Intuit sandbox (staging) to production, with the adapter registered but **dark** until a firm's
`connections.live_ledger` is turned on at its client-facing window. It holds no keys, account ids,
hosts beyond placeholders, or firm names.

## What the code already guarantees
- **Boot guards** (`kernel.config`): production refuses `fake_connector_dir`, refuses
  `qbo_environment = sandbox`, and needs `connections_redirect_base_url` once QuickBooks is
  registered; staging, local and test refuse `qbo_environment = production`.
- **Dark by default**: the adapter registers only when `qbo_client_id` and the secret are set, and
  every route and pull stays behind `connections.live_ledger` (default off, per firm).
- **Kill switch**: with `connections.live_ledger` off for a firm, a pull through a networked
  provider ends `connector_paused` before credentials are read or the provider is called; the flag
  is read past its cache at each pull.
- **Egress**: the connector reaches only the hosts the write-capability registry declares for it
  (DEC-582); the API and the worker refuse to start otherwise.

## Cutover steps (N, the other founder approving each change)

| # | Step | Where | Evidence |
|---|---|---|---|
| 1 | Intuit app assessment passed for the production app (security questionnaire, privacy policy and EULA URLs, the read-only scopes) | Intuit developer portal | the assessment approval, filed in the vault (`V-…`); the date here |
| 2 | One redirect URI registered with Intuit: `https://<connect host on the neutral portal domain>/v1/connections/callback` (never a firm's white-label host) | Intuit developer portal; `infra/modules/cloudfront-portal` routes it to the API | the registered URI in the app's settings |
| 3 | Production app keys into Secrets Manager (`abacus/production/qbo`: `client_id`, `client_secret`) by hand; never through Terraform or git | AWS console or `aws secretsmanager put-secret-value` from the vault | the secret's version id |
| 4 | Production tasks get `ABACUS_QBO_CLIENT_ID`, `ABACUS_QBO_CLIENT_SECRET`, `ABACUS_QBO_ENVIRONMENT=production`, `ABACUS_CONNECTIONS_REDIRECT_BASE_URL` (the compute stack, as staging's `qbo_enabled` does) | `infra/envs/production` | the task definition revision; the API and worker start (the boot guards passed) |
| 5 | The adapter is registered and dark: the connections catalogue lists QuickBooks Online; every firm's `connections.live_ledger` is off | `make go-live-check`; SIG-01-style read of the catalogue | the check's `integrations.*` rows |
| 6 | Kill-switch drill on staging (below) passed within the quarter | staging | the drill row |

Staging uses the sandbox app the same way: fill `abacus/staging/qbo`, then set `qbo_enabled = true`
in `infra/envs/staging` (an empty secret would stop every task from starting).

## Kill-switch drill (staging; target: pulls stop within one minute)
1. On the rehearsal firm, with `connections.live_ledger` on and a QuickBooks sandbox company
   connected, start an on-demand pull (AUD-06, or `POST /v1/engagements/{id}/connection/pulls`)
   and confirm it reaches the provider (the run's raw payload is recorded).
2. Note the time; `make flag FIRM=<rehearsal firm> FLAG=connections.live_ledger VALUE=false
   OPERATOR=<you> REASON="A-02-T33 kill-switch drill" APPROVED_BY=<other founder>`.
3. Start another pull at once, and let any queued scheduled pull run: each ends `failed` with
   `connector_paused` (the sync run's failure code), and the egress log shows no request to Intuit
   after the flip.
4. Record the seconds from the flip to the first `connector_paused` run below; turn the flag back
   on.

| Date | Environment | Flip at | First paused run at | Seconds | Egress after flip | Who |
|---|---|---|---|---|---|---|
| — | staging | — | — | — | — | not run: needs the sandbox app's secret and `qbo_enabled` on staging |

## Sandbox check from a laptop (F-09-T05, before staging)

`python -m abacus_tools.qbo_sandbox` runs the product's connector and egress client against
Intuit's sandbox with the app's Development keys: sign-in with PKCE and a checked `state`, the
token exchange, the companyinfo health read, the TrialBalance pull, a forced refresh-token
rotation and the revoke. It refuses anything but `sandbox` and reaches only the registry's
QuickBooks hosts (no Payments, no OpenID, no writes).

1. Use an Intuit app whose only scope is `com.intuit.quickbooks.accounting`. Scopes can't be
   removed once saved, so the Quick Start app (which asks for payments and OpenID too) is a
   throwaway; the app that goes to the assessment is a separate one.
2. Under Development keys > Redirect URIs, add `http://localhost:8765/callback`.
3. In a terminal of your own (never pasted into a chat, an ops request or a file in the repo):
   `export ABACUS_QBO_CLIENT_ID=… ABACUS_QBO_CLIENT_SECRET=…`
4. From `backend/`: `uv run python -m abacus_tools.qbo_sandbox connect`, sign in, pick the
   sandbox company. Then `health`, `trial-balance --start 2026-01-01 --end 2026-11-03`,
   `refresh --force` and `revoke`.

Tokens sit in `~/.abacus/qbo-sandbox.json` (0600, outside the repository) until `revoke` deletes
them. Production keys never go through this tool.
