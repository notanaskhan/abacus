# communications

Messages that leave the platform (ADR-065; SPEC-006). PROTECTED.

## Public interface (`api.py`)
- `send(ctx: AuthContext, engagement_id, Draft) -> MessageView`: the only send path. Its steps:
  1. refuse unless a person is making a live API request (ADR-005);
  2. authorise `message.send`;
  3. run the scope check;
  4. record the message, which is insert-only.
  - **Clean:** recorded `sent`, audited `message.sent`, and the outbox event `message.ready` is emitted.
  - **Violations:** recorded `blocked`, audited `message.blocked`, and `OutOfScope` raised (409 `out_of_scope`). A checker error blocks too.
- `check_scope(ctx, EngagementRef, text) -> list[Violation]`: deterministic. It flags the firm's other clients and entities (names of 4 characters or more, case-insensitive, whole words, with a stoplist); other ledgers' accounts (non-numeric codes, and names of 8 characters or more); and amounts not in the engagement's snapshots. Amounts are compared in cents; rounded amounts (whole units, `k`, `m`) match within their rounding; amounts under 100 and bare years are ignored.

- `comment_scope_kinds`: registered into requests as the check on firm comments shared with a client (SPEC-032 TASK-062 D1); a checker error returns `checker_error`, which blocks.

- `ses_identities() -> SesIdentityPort` (Q-01-T47; platform-ops contract 3.8), for R-01's ADM-10 sender domains:
  - `create_identity(domain=, mail_from_subdomain=)` requests Easy DKIM and a custom MAIL FROM domain, and returns the DNS records to publish (three DKIM CNAMEs, then the MAIL FROM MX and SPF TXT). It is idempotent for the same domain.
  - `identity_status(domain=)` returns `pending`, `verified` or `failed` for verification, DKIM and MAIL FROM.
  - `delete_identity(domain=)` is quiet when SES has no identity for the domain.
  - `SesIdentities` calls SES v2 through `kernel.storage.sesv2_client()` when `ses_configuration_set` is set. `InMemorySesIdentities` serves local and test runs. An SES error raises `SesIdentityUnavailable`, carrying the error code only. No tag or name carries a tenant: which firm owns a domain is R-01's record.

- `send_email(...)`: the one path to a transport. It refuses a suppressed address (Q-01-T46). For a synthetic firm it first routes the recipient to the mail sink (`sink.py`, F-04-T22):
  - an address on the sink domain is kept;
  - any other is rewritten to `<local-part>+<tenant-short>@<sink>`;
  - with no sink (an environment that set no `mail_sink_domain` and isn't local, test or evaluation), or an address the sink can't take, it is refused. The refusal is logged with IDs only, never the address.
- `send_notification_email(NotificationMail)` (P-01-T12): renders the published C16 template `notification.<kind>` with the four whitelisted values and sends through `send_email`. The message ID is the notification's ID.
- `FakeSesTransport` and `FakeSesEventQueue` (`fake_ses.py`, F-04.23; synthetic environments only): SES's contract at its edges. The mail goes to the local mailbox, and the delivery events SES would publish go to an in-memory queue that `drain_ses_events` reads. The mailbox simulator gives:
  - `bounce@` and `suppressionlist@`: a permanent bounce;
  - `complaint@`: a complaint.
- The harness reads the mail back with `abacus_tools.harness.mailbox.mail().latest(to)`: the local mailbox, or on staging the sink bucket (`mail_sink_bucket`).

## Rules
- COMM-001: nothing outside this module imports a mail or messaging library or emits `message.ready`.
- No transport yet: delivery comes with Phase 2 increments 2 and 8.
- The body is confidential and never logged. Violations are kinds and identifiers only.

## In the firm's name (SPEC-025 AC-8; TASK-043)
- **Client invitations:** "{firm} invites you to their FY{year} audit of {client}".
- **Staff invitations:** "{firm} invites you to join their workspace".
- **Sender:** the transport's `sender_name` is the firm's; the sending address stays ours until custom domains exist.
- **SPEC-027 (TASK-051):** `send_follow_up` (F-03-T16; was `send_reminder`) sends an overdue reminder in the firm's name (fixed template; item descriptions and a portal link) for a person or the engagement agent allowed `follow_up.send`, and records the message.

## Secure links (P-08-T21; SPEC-320 AC-14; DEC-329)
- `secure_links` (tenant, migration 0156): one link per portal email, for one contact and the address it went to; 14 days, single use, only the token's SHA-256 kept. `api.issue_secure_link(...)` makes one at send time (R-01's POR-20 emails) and returns the token once; `api.resolve_secure_link(tenant, token)` reads a live one server-side.
- Sign-in: identity's `start` with `link_token` uses `claim` through `identity.slots.register_link_claim`: every link that can't be used answers the same 404 `link_expired`; the address it was sent to uses it.
- `POST /v1/portal/links/renew` (pre-session, `secure_link_routes.py`): always 202 `{accepted: true}`, padded; at most 3 renewals per link per hour; nothing while the firm's sign-in is paused; an invitation token renews the expired invitation instead (identity, at most twice). The new link's token is issued at delivery (`portal.link_renew_requested` → `deliver_renewed_link`) and sent only to the original address from the C16 template `portal.link_renewed` (`firm_name`, `app_link`), imported per environment. No `messages` row: messages belong to an engagement, so the send is logged by link id (as sign-in codes are).
- `portal_mfa.reset_notice_requested` → `deliver_mfa_reset_notice`: the firm reset a client's second step; C16 `portal.mfa_reset_notice` (`firm_name`).
