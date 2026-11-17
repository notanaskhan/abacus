"""Relationship depth (T-06-T12; SPEC-702 F8, §4, AC-35; DEC-62, DEC-43; DEC-5521). Expand-only.

- `external_parties`: a person or organisation in a client's relationships who is not a client of
  the firm ("Not a Brightwater Hale client").
- `entity_relationships` gains an external party on either side (each side exactly one of an
  entity or an external party), `source`, `note`, the end (`ended_at`, `ended_by`, `end_reason`;
  ended, never deleted) and `version`. Existing P-07 rows read unchanged: their entity columns
  stay set and the new columns default.
- `entity_relationship_events` (insert-only): created, updated and ended, with before and after.
- `relationship_graph_layouts`: one user's node positions per client; never audited.
- A deferred constraint trigger caps ownership (`owner_of`, `gp_of`, `lp_of`) into one entity at
  100 percent on every date any of its edges is in force (`relationship_percent_exceeds`).

Revision ID: 0954
Revises: 0953
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0954"
down_revision = "0953"
branch_labels = None
depends_on = None

NEW_COLUMNS = (
    "from_external_party_id",
    "to_external_party_id",
    "source",
    "note",
    "ended_at",
    "ended_by",
    "end_reason",
    "version",
)
UPDATES = ("percent", "effective_to", "note", "ended_at", "ended_by", "end_reason", "version")
INSERTS = ("from_external_party_id", "to_external_party_id", "source", "note")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE external_parties (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_id uuid NOT NULL,
            display_name text NOT NULL CHECK (char_length(btrim(display_name)) BETWEEN 1 AND 200),
            kind text NOT NULL CHECK (kind IN ('individual', 'entity', 'trust', 'fund')),
            note text NULL CHECK (char_length(note) <= 500),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE entity_relationships
            ALTER COLUMN from_entity_id DROP NOT NULL,
            ALTER COLUMN to_entity_id DROP NOT NULL,
            ADD COLUMN from_external_party_id uuid NULL,
            ADD COLUMN to_external_party_id uuid NULL,
            ADD COLUMN source text NOT NULL DEFAULT 'manual'
                CHECK (source IN ('intake', 'manual', 'import')),
            ADD COLUMN note text NULL CHECK (char_length(note) <= 500),
            ADD COLUMN ended_at timestamptz NULL,
            ADD COLUMN ended_by uuid NULL,
            ADD COLUMN end_reason text NULL CHECK (char_length(end_reason) <= 500),
            ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            ADD CONSTRAINT entity_relationships_from_one_of CHECK (
                (from_entity_id IS NULL) <> (from_external_party_id IS NULL)
            ),
            ADD CONSTRAINT entity_relationships_to_one_of CHECK (
                (to_entity_id IS NULL) <> (to_external_party_id IS NULL)
            ),
            ADD CONSTRAINT entity_relationships_no_external_self CHECK (
                from_external_party_id IS NULL
                OR from_external_party_id IS DISTINCT FROM to_external_party_id
            ),
            ADD CONSTRAINT entity_relationships_end CHECK (
                (ended_at IS NULL) = (ended_by IS NULL)
                AND (ended_at IS NULL OR end_reason IS NOT NULL)
            ),
            ADD CONSTRAINT entity_relationships_from_party_fk
                FOREIGN KEY (tenant_id, from_external_party_id)
                REFERENCES external_parties (tenant_id, id),
            ADD CONSTRAINT entity_relationships_to_party_fk
                FOREIGN KEY (tenant_id, to_external_party_id)
                REFERENCES external_parties (tenant_id, id)
        """
    )
    # Ownership into one entity never exceeds 100% on any date an edge is in force. Deferred, so a
    # transfer (end one edge, start another) checks the result of the whole unit of work.
    op.execute(
        """
        CREATE FUNCTION entity_relationships_ownership_cap() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_total numeric;
        BEGIN
            IF NEW.kind NOT IN ('owner_of', 'gp_of', 'lp_of') OR NEW.to_entity_id IS NULL
               OR NEW.percent IS NULL THEN
                RETURN NULL;
            END IF;
            SELECT max(day_total) INTO v_total FROM (
                SELECT d.day, sum(r.percent) AS day_total
                  FROM public.entity_relationships r
                  JOIN (
                      SELECT s.effective_from AS day FROM public.entity_relationships s
                       WHERE s.tenant_id = NEW.tenant_id AND s.to_entity_id = NEW.to_entity_id
                  ) d ON r.effective_from <= d.day
                     AND (r.effective_to IS NULL OR r.effective_to >= d.day)
                 WHERE r.tenant_id = NEW.tenant_id
                   AND r.to_entity_id = NEW.to_entity_id
                   AND r.kind IN ('owner_of', 'gp_of', 'lp_of')
                   AND r.percent IS NOT NULL
                   AND r.ended_at IS NULL
                 GROUP BY d.day
            ) totals;
            IF v_total > 100 THEN
                RAISE EXCEPTION 'relationship_percent_exceeds' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER entity_relationships_ownership_cap "
        "AFTER INSERT OR UPDATE ON entity_relationships DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION entity_relationships_ownership_cap()"
    )
    op.execute(
        """
        CREATE TABLE entity_relationship_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            relationship_id uuid NOT NULL,
            event text NOT NULL CHECK (event IN ('created', 'updated', 'ended')),
            before jsonb NULL CHECK (before IS NULL OR jsonb_typeof(before) = 'object'),
            after jsonb NULL CHECK (after IS NULL OR jsonb_typeof(after) = 'object'),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'
                    AND actor_kind = current_setting('app.actor_kind', true)),
            actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)
                CHECK (actor_id = current_setting('app.actor_id', true)),
            on_behalf_of uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (event <> 'created' OR before IS NULL),
            FOREIGN KEY (tenant_id, relationship_id)
                REFERENCES entity_relationships (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION entity_relationship_events_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'entity_relationship_events is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER entity_relationship_events_immutable BEFORE UPDATE OR DELETE "
        "ON entity_relationship_events FOR EACH ROW "
        "EXECUTE FUNCTION entity_relationship_events_immutable()"
    )
    op.execute(
        "CREATE TRIGGER entity_relationship_events_no_truncate BEFORE TRUNCATE "
        "ON entity_relationship_events FOR EACH STATEMENT "
        "EXECUTE FUNCTION entity_relationship_events_immutable()"
    )
    op.execute(
        """
        CREATE TABLE relationship_graph_layouts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL,
            client_id uuid NOT NULL,
            positions jsonb NOT NULL CHECK (jsonb_typeof(positions) = 'object'),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, user_id, client_id),
            CHECK (user_id::text = current_setting('app.actor_id', true)),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    for table in ("external_parties", "entity_relationship_events", "relationship_graph_layouts"):
        tenant_table(op, table)
    insert_columns(
        op,
        "external_parties",
        ("tenant_id", "client_id", "display_name", "kind", "note", "created_by"),
    )
    insert_columns(
        op,
        "entity_relationship_events",
        ("tenant_id", "relationship_id", "event", "before", "after", "on_behalf_of"),
    )
    insert_only(op, "entity_relationship_events")
    insert_columns(
        op, "relationship_graph_layouts", ("tenant_id", "user_id", "client_id", "positions")
    )
    op.execute("REVOKE UPDATE, DELETE ON relationship_graph_layouts FROM abacus_app")
    op.execute("GRANT UPDATE (positions, updated_at) ON relationship_graph_layouts TO abacus_app")
    op.execute(f"GRANT INSERT ({', '.join(INSERTS)}) ON entity_relationships TO abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(UPDATES)}) ON entity_relationships TO abacus_app")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(UPDATES)}) ON entity_relationships FROM abacus_app")
    op.execute(f"REVOKE INSERT ({', '.join(INSERTS)}) ON entity_relationships FROM abacus_app")
    op.execute("DROP TABLE relationship_graph_layouts")
    op.execute("DROP TABLE entity_relationship_events")
    op.execute("DROP FUNCTION entity_relationship_events_immutable()")
    op.execute("DROP TRIGGER entity_relationships_ownership_cap ON entity_relationships")
    op.execute("DROP FUNCTION entity_relationships_ownership_cap()")
    op.execute(
        "DELETE FROM entity_relationships WHERE from_entity_id IS NULL OR to_entity_id IS NULL"
    )
    op.execute(
        """
        ALTER TABLE entity_relationships
            DROP CONSTRAINT entity_relationships_to_party_fk,
            DROP CONSTRAINT entity_relationships_from_party_fk,
            DROP CONSTRAINT entity_relationships_end,
            DROP CONSTRAINT entity_relationships_no_external_self,
            DROP CONSTRAINT entity_relationships_to_one_of,
            DROP CONSTRAINT entity_relationships_from_one_of,
            DROP COLUMN version,
            DROP COLUMN end_reason,
            DROP COLUMN ended_by,
            DROP COLUMN ended_at,
            DROP COLUMN note,
            DROP COLUMN source,
            DROP COLUMN to_external_party_id,
            DROP COLUMN from_external_party_id,
            ALTER COLUMN to_entity_id SET NOT NULL,
            ALTER COLUMN from_entity_id SET NOT NULL
        """
    )
    op.execute("DROP TABLE external_parties")
