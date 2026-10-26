"""Audit request context (G-02-T06; SPEC-349 AC-7, AC-9; DEC-60, DEC-418). Expand-only.

`audit_events` gains what ADM-07 shows about a person's request and the dimensions it filters on:
- `ip` (inet), `user_agent_family`, `device_label` ("Chrome · macOS"): from the HTTP edge. `ip`
  and `device_label` are personal data (Confidential): never logged.
- `session_id`, `auth_method`, `mfa_at`: the staff, portal or support session behind it.
- `client_id`, `office_id`: the client and office the event concerns, for the explorer's
  filters and walls (set by callers from G-02-T08).

New rule: the request-context columns are null unless a person or a support engineer acted
(`audit_events_request_context_is_a_persons`); agent, system and policy events never carry one.
History has none, so the check is validated at once.

Indexes for the explorer: the feed by business time, the Actor filter, a client's events and an
IP's events.

`audit_request_session(cookie_sha256, user_id)` (SECURITY DEFINER) answers the live staff session
whose current cookie that is, only when it is that user's: the unit of work records its id and
MFA time. The app never reads `auth_sessions` itself.

Insert-only triggers, RLS and the hash chain's guard are unchanged; the app may insert the new
columns. The chain's leaf moves to version 2 in the same change (`kernel/uow/chain.py`).

`down_revision` is 0160 on this branch (S9 wave C); the merge re-points it after the other
branches' migrations.

Revision ID: 0172
Revises: 0160
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0172"
down_revision = "0160"
branch_labels = None
depends_on = None

_BEFORE = (
    "tenant_id",
    "actor_kind",
    "actor_id",
    "action",
    "target_type",
    "target_id",
    "before_ref",
    "after_ref",
    "trace_id",
    "engagement_id",
    "work_item_id",
    "on_behalf_of_user_id",
    "policy_ref",
)
_CONTEXT = ("ip", "user_agent_family", "device_label", "session_id", "auth_method", "mfa_at")
_AFTER = (*_BEFORE, *_CONTEXT, "client_id", "office_id")
_INDEXES = (
    ("audit_events_feed", "(tenant_id, effective_at DESC, seq DESC)", ""),
    ("audit_events_actor_kind", "(tenant_id, actor_kind, seq DESC)", ""),
    ("audit_events_client", "(tenant_id, client_id, seq DESC)", "client_id IS NOT NULL"),
    ("audit_events_ip", "(tenant_id, ip)", "ip IS NOT NULL"),
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE audit_events
            ADD COLUMN ip inet NULL,
            ADD COLUMN user_agent_family text NULL
                CHECK (length(user_agent_family) BETWEEN 1 AND 40),
            ADD COLUMN device_label text NULL CHECK (length(device_label) BETWEEN 1 AND 80),
            ADD COLUMN session_id uuid NULL,
            ADD COLUMN auth_method text NULL CHECK (auth_method IN
                ('sso', 'email_code', 'passkey', 'totp', 'support', 'service')),
            ADD COLUMN mfa_at timestamptz NULL,
            ADD COLUMN client_id uuid NULL,
            ADD COLUMN office_id uuid NULL
        """
    )
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_request_context_is_a_persons "
        "CHECK (actor_kind IN ('human', 'support') OR (ip IS NULL AND user_agent_family IS NULL "
        "AND device_label IS NULL AND session_id IS NULL AND auth_method IS NULL "
        "AND mfa_at IS NULL))"
    )
    for name, columns, where in _INDEXES:
        predicate = f" WHERE {where}" if where else ""
        op.execute(f"CREATE INDEX {name} ON audit_events {columns}{predicate}")
    insert_columns(op, "audit_events", _AFTER)
    op.execute(
        """
        CREATE FUNCTION audit_request_session(p_cookie_sha256 text, p_user_id uuid)
        RETURNS TABLE (session_id uuid, mfa_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT s.id, s.mfa_at
              FROM public.auth_session_cookies c
              JOIN public.auth_sessions s ON s.id = c.session_id
             WHERE c.cookie_sha256 = p_cookie_sha256
               AND c.retired_at IS NULL
               AND s.user_id = p_user_id
               AND s.ended_at IS NULL
               AND clock_timestamp() < s.idle_expires_at
               AND clock_timestamp() < s.absolute_expires_at
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION audit_request_session(text, uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION audit_request_session(text, uuid) TO abacus_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION audit_request_session(text, uuid)")
    insert_columns(op, "audit_events", _BEFORE)
    for name, _, _ in reversed(_INDEXES):
        op.execute(f"DROP INDEX {name}")
    op.execute(
        "ALTER TABLE audit_events DROP CONSTRAINT audit_events_request_context_is_a_persons"
    )
    op.execute(
        "ALTER TABLE audit_events DROP COLUMN office_id, DROP COLUMN client_id, "
        "DROP COLUMN mfa_at, DROP COLUMN auth_method, DROP COLUMN session_id, "
        "DROP COLUMN device_label, DROP COLUMN user_agent_family, DROP COLUMN ip"
    )
