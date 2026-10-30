"""C7 v1.1's two markers on an envelope (N-02-T25; N-02 §4.4 v1.1; DEC-85; DEC-1285).
Expand-only.

- **Superseded for an amount change** (T-01's 8879 binding): `superseded_at`, `superseded_reason`
  and `superseded_binding_ref` (0292) are set by the system only and never cleared or changed
  once set. Every gate consumer treats a superseded envelope as unmet; its evidence stays.
- **Retention, forward only**: `envelopes.retain_until`, the date the envelope's stored records
  are locked until when a consumer (T-01's filing date, Q-05) extends it past the policy floor;
  it can be set or moved later, never earlier and never cleared.

One BEFORE UPDATE trigger holds both, for every role, whatever the caller.

Revision ID: 0432
Revises: 0431
"""

from __future__ import annotations

from alembic import op

revision = "0432"
down_revision = "0431"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE envelopes ADD COLUMN retain_until date NULL")
    op.execute(
        """
        CREATE FUNCTION envelopes_v11_markers() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF OLD.superseded_at IS NOT NULL AND (
                   NEW.superseded_at IS DISTINCT FROM OLD.superseded_at
                OR NEW.superseded_reason IS DISTINCT FROM OLD.superseded_reason
                OR NEW.superseded_binding_ref IS DISTINCT FROM OLD.superseded_binding_ref) THEN
                RAISE EXCEPTION 'a superseded envelope stays superseded'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.superseded_at IS NULL AND NEW.superseded_at IS NOT NULL
               AND current_setting('app.actor_kind', true) IS DISTINCT FROM 'system' THEN
                RAISE EXCEPTION 'only the system supersedes an envelope'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.retain_until IS NOT NULL
               AND (NEW.retain_until IS NULL OR NEW.retain_until < OLD.retain_until) THEN
                RAISE EXCEPTION 'an envelope''s retention only extends'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER envelopes_v11_markers BEFORE UPDATE ON envelopes "
        "FOR EACH ROW EXECUTE FUNCTION envelopes_v11_markers()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER envelopes_v11_markers ON envelopes")
    op.execute("DROP FUNCTION envelopes_v11_markers()")
    op.execute("ALTER TABLE envelopes DROP COLUMN retain_until")
