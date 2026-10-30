---
id: TASK-2150
title: N-02-T19 rework - provider status truth for DocuSeal (poll, verified webhook hint; ADR-342)
spec: SPEC-381
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T19
branch: n02-t19-docuseal
created: 2026-10-30
updated: 2026-10-30
---

## Objective

ADR-342 replaced DocuSign with DocuSeal. Rework N-02-T19 (#776, TASK-2140) against the
re-scoped row. Acceptance (backlog row): "A webhook (if mounted) changes nothing until the poll
confirms, a forged one is refused, and a duplicate state change is recorded once."

DocuSeal signs every webhook (its "Use webhooks" guide): `X-Docuseal-Signature:
<unix seconds>.<hex HMAC-SHA256(key, "<unix seconds>.<raw body>")>`, with a 5-minute tolerance
and the `whsec_…` key shown under the webhook's Security → HMAC tab. That is the verifiable secret
ADR-342 asked N-02-T06 to find, so the receiver's helpers are built now. The route itself stays
unmounted: ADR-152 (and its amendment) is still `proposed`, and ADR-342 mounts the receiver only
under an accepted amendment. Status stays poll-only.

## Plan

- `signatures/status_poll.py`:
  - drop DocuSign Connect (`verify_connect`, `connect_event`, `ConnectEvent`);
  - `verify_webhook(body, header, keys, now)`: parse `<ts>.<sig>`, refuse a timestamp more than
    300 s from `now` (replay), compare the hex HMAC in constant time against every configured key
    (rotation); empty body, header or keys refuse;
  - `webhook_event(body)`: only the submission id (`data.submission.id` for `form.*`,
    `data.id` for `submission.*`) and a stable event id (sha256 of event type, submission,
    submitter and timestamp); anything else in the body is ignored;
  - `record_connect_hint` → `record_provider_hint` (same SQL: once per provider event id per
    firm; changes no envelope state; signals the workflow only when new);
  - docstring: poll-only until ADR-152's amendment is accepted.
- `docs/adr/ADR-152-…md` (proposed): the amendment's receiver retargeted to
  `POST /v1/webhooks/docuseal`, verified by DocuSeal's signed header with replay tolerance.
- Tests: `tests/unit/signatures/test_n02t19_webhook_hint.py` (pure: forged, tampered, stale,
  rotated keys, stable ids) replaces the Connect test; integration
  `tests/integration/backfill/test_n02t19_provider_hint.py` (a duplicate is recorded once, the
  envelope's status is untouched, the workflow is signalled once).
- DEC-1277. No migration, no flag, no route.
- Rollback: revert the PR.

## Human to-dos

- Accept ADR-152 and its amendment to mount the receiver (then a route task wires
  `verify_webhook` + `webhook_event` + `record_provider_hint`, rate-limited, empty 202).
- On the DocuSeal sandbox: confirm the HMAC key is used as its literal string (including the
  `whsec_` prefix) and that `form.*` payloads carry `data.submission.id`.
- Keep the webhook key in the vault and in the firm's sealed install, never in git.

## Progress log

- 2026-10-30: plan written from DocuSeal's webhook guide and OpenAPI spec.
- 2026-10-30: built. `tests/unit/signatures` 16 pass (7 webhook); integration
  `test_n02t19_provider_hint.py` 2 pass, `test_n02t14_envelope_workflow.py` 4 and platform
  schedules pass; ruff, whole-tree pyright, lint-imports, banned_patterns, validate_docs,
  scope_guards and secrets_scan clean (register_ids flags main's DEC-836 duplicate only). The four
  `test_worker_screening` failures are main's (tax `WORKFLOWS`), identical on base 27e096eff.
  SPEC-381 §8 and ADR-152's proposed amendment now name `POST /v1/webhooks/docuseal`.
