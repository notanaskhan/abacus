"""A-09-T11 (S46; TASK-8092; SPEC-658; ADR-045, A-09 relaxes it for OneWorld; red):
`connection_coverage`, a connection-index change, expand-only.

A NetSuite OneWorld connection reads every subsidiary of a group, so "one live ledger per entity"
moves from the connection to the entities it covers:

- `connection_entity_coverage(connection_id, client_entity_id, category, live)`: the entities a
  connection covers. Backfilled with each connection's own entity (live while the connection is
  not revoked); a covering connection adds its other entities when a consolidation attaches them
  (A-09-T13).
- A partial unique index: at most one live ledger coverage row per (tenant, entity), so a second
  live ledger for a covered subsidiary is refused (a bank feed may sit beside others, as today).
- Triggers keep it in step with `connections`: an insert covers the connection's own entity, a
  status change sets `live` (`status <> 'revoked'`) on every row of the connection.
- `connections_one_live_ledger` stays until the post-window contract step drops it.

Revision ID: 0897
Revises: 0896
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0897"
down_revision = "0896"
branch_labels = None
depends_on = None

_CATEGORIES = "('ledger', 'bank_feed', 'card_feed', 'sales', 'payroll', 'hr', 'ticketing', 'grc')"

_SYNC = """
CREATE FUNCTION connection_coverage_sync() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.connection_entity_coverage
            (tenant_id, connection_id, client_entity_id, category, live)
        VALUES (NEW.tenant_id, NEW.id, NEW.client_entity_id, NEW.category,
                NEW.status <> 'revoked');
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        UPDATE public.connection_entity_coverage
           SET live = (NEW.status <> 'revoked')
         WHERE tenant_id = NEW.tenant_id AND connection_id = NEW.id;
    END IF;
    RETURN NEW;
END
$$
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE connection_entity_coverage (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            category text NOT NULL CHECK (category IN {_CATEGORIES}),
            live boolean NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, connection_id, client_entity_id),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    # The backfill reads every firm's connections as the owner: forced RLS is lifted for the
    # copy and restored before anything else runs (the 0068 pattern).
    op.execute("ALTER TABLE connections NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "INSERT INTO connection_entity_coverage (tenant_id, connection_id, client_entity_id, "
        "category, live) SELECT tenant_id, id, client_entity_id, category, status <> 'revoked' "
        "FROM connections"
    )
    op.execute("ALTER TABLE connections FORCE ROW LEVEL SECURITY")
    tenant_table(op, "connection_entity_coverage")
    op.execute(
        "CREATE UNIQUE INDEX connection_coverage_one_live ON connection_entity_coverage "
        "(tenant_id, client_entity_id, category) WHERE live AND category = 'ledger'"
    )
    op.execute(_SYNC)
    op.execute("REVOKE ALL ON FUNCTION connection_coverage_sync() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER connection_coverage_sync AFTER INSERT OR UPDATE OF status ON connections "
        "FOR EACH ROW EXECUTE FUNCTION connection_coverage_sync()"
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON connection_entity_coverage FROM abacus_app")
    insert_columns(
        op,
        "connection_entity_coverage",
        ("tenant_id", "connection_id", "client_entity_id", "category", "live"),
    )
    op.execute("GRANT UPDATE (live) ON connection_entity_coverage TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TRIGGER connection_coverage_sync ON connections")
    op.execute("DROP FUNCTION connection_coverage_sync()")
    op.execute("DROP TABLE connection_entity_coverage")
