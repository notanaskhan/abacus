---
id: TASK-3044
title: QuickBooks connector reads Intuit's discovery document and logs intuit_tid; draft Intuit assessment answers
spec: A-02-T26 (connector), F-09-T05, F-09-T11 (Intuit part)
acceptance_criteria: [every Intuit technical question answers yes from code on main]
risk_zone: red
status: in-review
branch: qbo-discovery-tid
created: 2026-11-03
updated: 2026-11-03
---

## Objective
Close the two connector gaps Intuit's app assessment asks about (discovery document, `intuit_tid`)
and draft the questionnaire answers from the code.

## Scope
**In**
- `quickbooks_online.py`: OAuth endpoints from Intuit's discovery document, cached a day per
  environment, pinned fallback; `intuit_tid` logged per response.
- Registry: `developer.intuit.com` (GET only) for `quickbooks_online`; regenerated
  `_capabilities.py`; `qbo_adapter._HOSTS`.
- `docs/ops/vendors/intuit-app-assessment.md` (draft answers); DEC-2083.

**Out**
- Submitting the questionnaire, the production app, domains and legal URLs (Ayush; F-09-T09,
  counsel rows). The other vendors in F-09-T11 (SES, Bedrock, Entra, WorkOS, DocuSeal).

## Plan
- [x] Plan approved by human (Ayush, 2026-11-03: "Yes, do both")

1. [x] Discovery: GET only, through the connector's own egress client; endpoints accepted only
   when HTTPS on an `*.intuit.com` host with a plain path (regex, CONN-001 bans URL libraries);
   anything else, or an unreadable document, uses the pinned endpoints and is not cached. The
   egress allowlist and read-POST pairs stay the ceiling: a moved token or revoke path is refused
   (fail closed) until the registry is changed.
2. [x] `intuit_tid`: read case-insensitively, kept only when `[A-Za-z0-9-]{1,64}`, logged as
   `qbo.response` with endpoint and status (warning at 4xx/5xx, info otherwise). No token, body,
   realm or amount is logged.
3. [x] Tests in `tests/unit/connections/test_qbo_connector.py` (discovery used and cached,
   fallback not cached, six hostile endpoint shapes, tid logged and nothing else, hostile tid
   dropped, host declared for this connector only and never a read POST).

Rollback: revert the commit; the pinned endpoints are the previous behaviour.

## Progress log
- 2026-11-03: built. Ruff, pyright, lint-imports; QBO, C20, connections, integrations, egress,
  banned-pattern and connector-conformance suites pass (3,328 + 239 tests). First draft used
  `urllib.parse` and tripped CONN-001; replaced by a regex. Intuit's live discovery documents
  (sandbox and production) were fetched: their three endpoints equal the pinned ones, and their
  `intuit_tid` (`1-6ae9db5b-…`) fits the check.
