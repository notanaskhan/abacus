"""Q-02-T08 (TASK-1210; SPEC-036 AC-5): citations written by a shadow run stay hidden.

- `citations.shadow`: the citation was written by an agent run that started in shadow
  (`agent_runs.shadow`, 0056), or succeeds one that was (a move keeps it). Every firm-facing
  citation reader leaves these out, as the agents module's readers leave out the runs' outputs.
  The app's insert grant gains the column; the writer sets it from the run, never the caller.
- Existing rows are back-filled from `agent_runs`, then successors from their predecessors.
  The owner is held to row-level security, so the two tables read are unforced for the
  statements (as 0068 and 0082 do) and the update guard stands aside for them only.
- `citations_shadow_follows` (BEFORE INSERT, security invoker): a row whose run started in
  shadow, or whose predecessor is shadow, is stored shadow whatever the writer passed, so the
  database keeps the flag right even if a writer forgets it (security review, TASK-1210).

Revision ID: 0158
Revises: 0157
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0158"
down_revision = "0157"
branch_labels = None
depends_on = None

_INSERT_V1 = (
    *("id", "tenant_id", "engagement_id", "work_item_id", "client_id"),
    *("cited_from_type", "cited_from_id", "cited_from_ref", "cited_from_locator", "n", "kind"),
    *("source_type", "source_id", "source_version", "locator", "match_id", "quote_sha256"),
    *("value_text", "verified", "verification_reason", "verifier_version", "supersedes_id"),
    *("created_by_kind", "created_by_user_id", "created_by_run_id", "on_behalf_of_user_id"),
)


def upgrade() -> None:
    op.execute("ALTER TABLE citations ADD COLUMN shadow boolean NOT NULL DEFAULT false")
    for table in ("citations", "agent_runs"):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE citations DISABLE TRIGGER citations_immutable_update")
    op.execute(
        """
        UPDATE citations c SET shadow = true
          FROM agent_runs r
         WHERE r.id = c.created_by_run_id AND r.tenant_id = c.tenant_id AND r.shadow
        """
    )
    op.execute(
        """
        WITH RECURSIVE chain AS (
            SELECT id FROM citations WHERE shadow
            UNION
            SELECT c.id FROM citations c JOIN chain ON c.supersedes_id = chain.id
        )
        UPDATE citations SET shadow = true WHERE id IN (SELECT id FROM chain) AND NOT shadow
        """
    )
    op.execute("ALTER TABLE citations ENABLE TRIGGER citations_immutable_update")
    for table in ("citations", "agent_runs"):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE FUNCTION citations_shadow_follows() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.shadow THEN
                RETURN NEW;
            END IF;
            NEW.shadow := EXISTS (
                SELECT 1 FROM public.agent_runs r
                 WHERE r.id = NEW.created_by_run_id AND r.tenant_id = NEW.tenant_id AND r.shadow
            ) OR EXISTS (
                SELECT 1 FROM public.citations p
                 WHERE p.id = NEW.supersedes_id AND p.tenant_id = NEW.tenant_id AND p.shadow
            );
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER citations_shadow_follows BEFORE INSERT ON citations "
        "FOR EACH ROW EXECUTE FUNCTION citations_shadow_follows()"
    )
    insert_columns(op, "citations", (*_INSERT_V1, "shadow"))


def downgrade() -> None:
    insert_columns(op, "citations", _INSERT_V1)
    op.execute("DROP TRIGGER citations_shadow_follows ON citations")
    op.execute("DROP FUNCTION citations_shadow_follows()")
    op.execute("ALTER TABLE citations DROP COLUMN shadow")
