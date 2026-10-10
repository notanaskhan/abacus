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

## Rules
- COMM-001: nothing outside this module imports a mail or messaging library or emits `message.ready`.
- No transport yet: delivery comes with Phase 2 increments 2 and 8.
- The body is confidential and never logged. Violations are kinds and identifiers only.

## In the firm's name (SPEC-025 AC-8; TASK-043)
- **Client invitations:** "{firm} invites you to their FY{year} audit of {client}".
- **Staff invitations:** "{firm} invites you to join their workspace".
- **Sender:** the transport's `sender_name` is the firm's; the sending address stays ours until custom domains exist.
- **SPEC-027 (TASK-051):** `send_reminder` sends an overdue reminder in the firm's name (fixed template; item descriptions and a portal link) for a person or the engagement agent allowed `follow_up.send`, and records the message.
