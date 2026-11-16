# Support (v1)

| Field | Value |
|---|---|
| Register row | epic contract (G-04 §8.1) |
| Version | v1 |
| Status | stub (G-04-T03) |
| Provider epic | G-04 (N: chat, help, status, publications; AY: SHL-05) |
| Consumers | SHL-05, ADM-06 (support-access block), PLT-01 (Support queue, Status, Publications), K-05 |
| Flag | `support.panel_v2` (per firm); console side `platform.console` |
| Spec | `docs/specs/SPEC-680-g04-platform-console-plan-usage-support.md` (AC-44 to AC-58), `SPEC-681` (support sessions v2) |
| ADRs | ADR-028, ADR-145, ADR-300 (P-62), ADR-139; DEC-60, DEC-61, DEC-72 |

## 1. Purpose
A firm user's one thread with a named person at Accrued Support, help articles as global content with screen context, firm-facing system status, and the support-session v2 fields the drawer and ADM-06 show.

## 2. Who may call it
Firm routes answer: a client principal 404 (the portal never mounts SHL-05, INV-4); the action on the firm; 404 while `support.panel_v2` is off; then 501 naming G-04-T10. Console routes are staff actions on the staff token (see `platform-console.md` §2). Code: `platform/support_contract.py` (firm), `platform/console_contract.py` (staff).

| Operation | Method and path | Action | Task |
|---|---|---|---|
| Thread | GET `/v1/support/conversation` (OWN; `availability`, session cards, suggestions) | `support.chat` | T10 |
| Send | POST `/v1/support/conversation/messages` (1 to 4,000 characters, Idempotency-Key, 30 per 10 minutes; 429) | `support.chat` | T10 |
| Help | GET `/v1/help/articles?context=&q=` · GET `/v1/help/articles/{slug}` | `help.read` | T10 |
| Status | GET `/v1/status` | `status.read` | T10 |
| Support queue (staff) | GET `/v1/platform/support/conversations` · GET `…/{id}` · POST `…/{id}/messages` | `platform_support.reply` | T10 |
| Incidents (staff) | GET · POST `/v1/platform/status/incidents` · POST `…/{id}/updates` · `…/{id}/resolve` | `platform_status.manage` | T10 |
| Publications (staff) | GET `/v1/platform/publications?status=draft` · POST `…/{kind}/{id}/publish` · `…/withdraw` (409 `approver_is_drafter`) | `platform_content.read` · `platform_content.publish` | T10 |
| Sessions v2 (firm) | GET `/v1/support-sessions` adds `scope_label`, `approver_role`, `conversation_id`; POST `…/{id}/decline` | `support_session.read` · `support_session.decline` | T05 |

## 3. Models
`ConversationOut` (`AvailabilityOut`, `SupportMessageOut`, `SessionCardOut`), `SupportMessageIn`, `HelpArticlesOut` (`HelpGroupOut`, `HelpArticleSummaryOut`), `HelpArticleOut` (structured `HelpBlockOut`s: heading, paragraph, list, note, screen link; never HTML), `FirmStatusOut` (`StatusComponentOut`), and the console's `QueueConversationsOut`, `QueueConversationDetailOut`, `StaffReplyIn`, `StatusIncidentsOut`, `StatusIncidentIn`, `ConsolePublicationsOut`, `ConsolePublishIn`. Message bodies are `confidential`: never logged, audited or put in a notification (DEC-60, DEC-61); no C17 tool or `ai_gateway` purpose reads them (AC-49). Fixtures: the seven SHL-05 e components with the CCH note, the help groups, the two suggestion cards (`platform/g04_fixtures.py`).

## 4. Status words
`support_availability`, `status_component`, `support_session` (DF-31, G-04-T02).
