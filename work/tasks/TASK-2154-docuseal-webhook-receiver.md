---
id: TASK-2154
title: ADR-152 accepted - the DocuSeal webhook receiver (DEC-1281)
spec: SPEC-381
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T19
branch: adr-152-docuseal-webhook
created: 2026-10-30
updated: 2026-10-30
---

## Objective

Ayush accepted ADR-152 and its amendment on 2026-10-30. Mount the DocuSeal webhook receiver the
amendment describes, using the T19 helpers (`verify_webhook`, `webhook_event`,
`record_provider_hint`), with nothing written before the signature holds and the body never
trusted for state (ADR-041).

## Plan

- **Path** `POST /v1/webhooks/docuseal/{tenant_id}/{install_id}` (DEC-1281: forced row security
  means the firm must be known before its install key can be read; DocuSeal allows a webhook per
  install).
- `identity/routing.py`: `PROVIDER_WEBHOOK` marker, accepted on that path only; ROUTE-001
  exception list (`banned_patterns.PUBLIC_ROUTE_EXCEPTIONS`); route-introspection checks know the
  marker.
- `signatures/webhook.py` (receiver), `webhook_routes.py` (route, empty answers);
  `integrations.esign_webhook_secret` (exactly this install, connected, W7 open) given to
  signatures through a slot the API registers (`register_esign_webhook`; ADR-008).
- `DocuSealAccount.webhook_keys`; `abacus_tools.esign_install` seals keys from
  `ABACUS_ESIGN_INSTALL_WEBHOOK_KEYS`; staging maps the secret's `webhook_keys` into the ops task
  behind `docuseal_webhook_enabled`.
- WAF: a rate rule, 300 per 5 minutes per IP on `/v1/webhooks/`.
- ADR-152 `status: accepted` with the amendment folded in; README index; C7 contract row; SPEC-381
  line; DEC-1281. API client regenerated (`make generate`).
- Tests: integration through the real route (signed, retried, forged, stale, unsigned, wrong
  install or firm, kill switch off, keyless install, oversized, unknown submission, per-envelope
  cap); unit for webhook keys; route suites updated for the marker.
- No migration. Rollback: revert; the firm keeps polling.

## Progress log

- 2026-10-30: built. Integration 6 passed first run. The public-route sweep found an unsigned
  request reached the database lookup (500 with no database): now a missing or malformed
  signature header is refused before any lookup.
