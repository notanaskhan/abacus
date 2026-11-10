"""P-10-T26 portal remainder (S33 partials round 2; TASK-6570; SPEC-647 AC-T5; DEC-3170): the
portal session lookup also answers the access token's expiry.

`portal_invitee_resolve` (0140) gains `access_expires_at`, so a portal stream closes 30 seconds
before the portal access token expires, as the firm app's do (DEC-3141). The function's checks are
unchanged: a live portal session on its pinned host with every expiry still ahead. A return type
cannot change in place, so the function is dropped and created again, then its grants restored.

Revision ID: 0762
Revises: 0761
"""

from __future__ import annotations

from alembic import op

revision = "0762"
down_revision = "0761"
branch_labels = None
depends_on = None

_BODY = """
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        #variable_conflict use_column
        BEGIN
            RETURN QUERY
            SELECT s.id, s.user_id, s.tenant_id, u.email, s.mfa_at, s.device_trusted_at{expiry}
              FROM public.auth_sessions s JOIN public.users u ON u.id = s.user_id
             WHERE s.access_sha256 = p_access_sha256 AND s.surface = 'portal'
               AND s.host = lower(p_host) AND s.ended_at IS NULL
               AND s.access_expires_at > clock_timestamp()
               AND s.idle_expires_at > clock_timestamp()
               AND s.absolute_expires_at > clock_timestamp();
        END $$
"""
_HEAD = (
    "CREATE FUNCTION portal_invitee_resolve(p_access_sha256 text, p_host text) "
    "RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid, email text, "
    "mfa_at timestamptz, device_trusted_at timestamptz"
)
# Static SQL only: the two shapes differ by one fixed column, no input reaches the text.
_WITH_EXPIRY = (
    _HEAD + ", access_expires_at timestamptz)" + _BODY.replace("{expiry}", ", s.access_expires_at")
)
_WITHOUT_EXPIRY = _HEAD + ")" + _BODY.replace("{expiry}", "")


def _create(sql: str) -> None:
    op.execute(sql)
    op.execute("REVOKE ALL ON FUNCTION portal_invitee_resolve(text, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION portal_invitee_resolve(text, text) TO abacus_app")


def upgrade() -> None:
    op.execute("DROP FUNCTION portal_invitee_resolve(text, text)")
    _create(_WITH_EXPIRY)


def downgrade() -> None:
    op.execute("DROP FUNCTION portal_invitee_resolve(text, text)")
    _create(_WITHOUT_EXPIRY)
