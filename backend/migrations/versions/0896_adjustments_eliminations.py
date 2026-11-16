"""A-09-T10 (S46; TASK-8091; SPEC-658; C8 v1.1; ADR-040, DEC-69; red): `adjustments_eliminations`,
expand-only.

Consolidation eliminations ride the adjustments tables (C8 kind `elimination`):

- `proposed_entries` gains `consolidation_id` (the consolidation an elimination belongs to),
  `posting_target` (only `consolidation_layer`) and `display_code` (the worksheet's "E1a").
- `proposed_entry_lines` gains `client_entity_id` (the entity a line eliminates) and
  `consolidation_level` (1 to 3, the tier it posts at).
- `pe_posting_dormant` is replaced: an entry still never reaches posted, failed_post or reversed,
  except an elimination whose posting target is the consolidation layer. Posting there writes
  Accrued's own consolidation layer, never a client system (ADR-040 stands). A posting target
  needs kind `elimination` and a consolidation.
- A deferred constraint trigger refuses, at commit, a line whose entity is not one of its
  entry's consolidation entities, and a line with an entity on an entry with no consolidation.

Every existing row satisfies the new checks (no column has a value yet), so nothing is rewritten.

Revision ID: 0896
Revises: 0895
"""

from __future__ import annotations

from alembic import op

revision = "0896"
down_revision = "0895"
branch_labels = None
depends_on = None

_DORMANT_BEFORE = "CHECK (status NOT IN ('posted', 'failed_post', 'reversed'))"
_DORMANT_AFTER = (
    "CHECK (status NOT IN ('posted', 'failed_post', 'reversed') "
    "OR (kind = 'elimination' AND posting_target = 'consolidation_layer'))"
)

_LINE_ENTITY = """
CREATE FUNCTION proposed_entry_line_entity() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    v_consolidation uuid;
BEGIN
    IF NEW.client_entity_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT consolidation_id INTO v_consolidation FROM public.proposed_entries
     WHERE tenant_id = NEW.tenant_id AND id = NEW.entry_id;
    IF v_consolidation IS NULL OR NOT EXISTS (
        SELECT 1 FROM public.consolidation_entities ce
         WHERE ce.tenant_id = NEW.tenant_id AND ce.consolidation_id = v_consolidation
           AND ce.client_entity_id = NEW.client_entity_id
    ) THEN
        RAISE EXCEPTION 'line_entity_outside_consolidation' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE proposed_entries
            ADD COLUMN consolidation_id uuid NULL,
            ADD COLUMN posting_target text NULL
                CONSTRAINT pe_posting_target CHECK (posting_target = 'consolidation_layer'),
            ADD COLUMN display_code text NULL
                CONSTRAINT pe_display_code CHECK (display_code ~ '^E[1-9][0-9]?[a-z]?$'),
            ADD CONSTRAINT pe_consolidation_fk FOREIGN KEY (tenant_id, consolidation_id)
                REFERENCES consolidations (tenant_id, id),
            ADD CONSTRAINT pe_target_needs_elimination CHECK (
                posting_target IS NULL OR (kind = 'elimination' AND consolidation_id IS NOT NULL)
            ),
            ADD CONSTRAINT pe_consolidation_only_eliminations
                CHECK (consolidation_id IS NULL OR kind = 'elimination')
        """
    )
    op.execute("ALTER TABLE proposed_entries DROP CONSTRAINT pe_posting_dormant")
    op.execute(f"ALTER TABLE proposed_entries ADD CONSTRAINT pe_posting_dormant {_DORMANT_AFTER}")
    op.execute(
        """
        ALTER TABLE proposed_entry_lines
            ADD COLUMN client_entity_id uuid NULL,
            ADD COLUMN consolidation_level integer NULL
                CONSTRAINT pel_consolidation_level CHECK (consolidation_level BETWEEN 1 AND 3),
            ADD CONSTRAINT pel_entity_fk FOREIGN KEY (tenant_id, client_entity_id)
                REFERENCES client_entities (tenant_id, id),
            ADD CONSTRAINT pel_level_needs_entity
                CHECK (consolidation_level IS NULL OR client_entity_id IS NOT NULL)
        """
    )
    op.execute(_LINE_ENTITY)
    op.execute("REVOKE ALL ON FUNCTION proposed_entry_line_entity() FROM PUBLIC")
    op.execute(
        "CREATE CONSTRAINT TRIGGER proposed_entry_line_entity AFTER INSERT OR UPDATE "
        "OF client_entity_id ON proposed_entry_lines DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION proposed_entry_line_entity()"
    )
    op.execute(
        "GRANT INSERT (consolidation_id, posting_target, display_code) ON proposed_entries "
        "TO abacus_app"
    )
    op.execute(
        "GRANT INSERT (client_entity_id, consolidation_level) ON proposed_entry_lines TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (client_entity_id, consolidation_level) ON proposed_entry_lines TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER proposed_entry_line_entity ON proposed_entry_lines")
    op.execute("DROP FUNCTION proposed_entry_line_entity()")
    op.execute(
        "ALTER TABLE proposed_entry_lines DROP CONSTRAINT pel_level_needs_entity, "
        "DROP CONSTRAINT pel_entity_fk, DROP COLUMN consolidation_level, "
        "DROP COLUMN client_entity_id"
    )
    op.execute("ALTER TABLE proposed_entries DROP CONSTRAINT pe_posting_dormant")
    op.execute(f"ALTER TABLE proposed_entries ADD CONSTRAINT pe_posting_dormant {_DORMANT_BEFORE}")
    op.execute(
        "ALTER TABLE proposed_entries DROP CONSTRAINT pe_consolidation_only_eliminations, "
        "DROP CONSTRAINT pe_target_needs_elimination, DROP CONSTRAINT pe_consolidation_fk, "
        "DROP COLUMN display_code, DROP COLUMN posting_target, DROP COLUMN consolidation_id"
    )
