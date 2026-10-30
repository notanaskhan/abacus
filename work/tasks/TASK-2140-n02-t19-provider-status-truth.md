---
id: TASK-2140
title: N-02-T19 Provider status truth (poll-only until ADR-152's amendment is accepted)
spec: SPEC-381
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T19
branch: s16-n02-t19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Acceptance (backlog row): "A forged Connect call is refused, a genuine one changes nothing until
the poll confirms, and a duplicate event is recorded once."

## Plan
- ADR-152's amendment (the Connect receiver) is `proposed`: it binds nothing, so no
  unauthenticated route is mounted. The row's own fallback applies: poll-only.
- `signatures/status_poll.py`: `EnvelopeStatusPoll` Schedule (`envelope_status_poll:platform`, 5
  min, background) signalling `provider_hint` to each open DocuSign envelope of firms with
  `signatures.docusign` on; `hint_envelope` for the portal return (N-02-T24); `verify_connect`
  (constant-time HMAC, rotating keys), `connect_event` (envelope id and a stable event id only),
  `record_connect_hint` (once per provider event id, audited, signals; changes no state).
- Tests: `tests/unit/signatures/test_n02t19_connect_hint.py`.

## Human to-dos
- Accept or refuse ADR-152's amendment. On acceptance: mount `POST /v1/webhooks/docusign-connect`
  outside `AbacusRouter` on the ROUTE-001 list, resolve the firm from the provider envelope id
  through a definer function, rate-limit, answer an empty 202, and call `verify_connect` →
  `record_connect_hint`.

## Progress log
- 2026-10-30: built; unit tests pass (3). Schedule and replay at the end review.
