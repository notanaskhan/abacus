"""CLI-06's single intake drafts (P-07-T42; P-07 §4.2 M8; DEC-374, DEC-430).

- New `client_intake_drafts`: the intake wizard's autosaved state (entity, relationships,
  contacts, services, conflicts, review), its owner's only (the service filters by
  `created_by`; RLS by tenant). Same shape and purge rule as `engagement_drafts` (0131): the
  payload holds identifiers and typed values only (no TIN, no free text beyond names), `version`
  is the autosave's `seen_version`, a draft is discarded (`discarded_at`) or committed
  (`committed_at`, `committed_client_id`), never deleted by the app; the purge 30 days later is
  operational (OQ-17).
- `result` is what the commit answered (identifiers only: the client, the entity, engagements,
  work items, the conflict check, the acceptance record), so a committed draft answers the same
  again whatever key a retry carries. It is written once, with `committed_at`, when the
  payload is emptied (the client tables hold the data then; security review L5).
- A trigger refuses any UPDATE of a committed or discarded draft (security review L1): both are
  final, whatever the app's grants allow.

Revision ID: 0177
Revises: 0175
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0177"
down_revision = "0175"
branch_labels = None
depends_on = None

_STEPS = "'entity', 'relationships', 'contacts', 'services', 'conflicts', 'review'"
_UPDATES = (
    "step",
    "payload",
    "version",
    "saved_at",
    "discarded_at",
    "committed_at",
    "committed_client_id",
    "result",
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE client_intake_drafts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            created_by uuid NOT NULL,
            step text NOT NULL DEFAULT 'entity' CHECK (step IN ({_STEPS})),
            payload jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 32768),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            saved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            discarded_at timestamptz NULL,
            committed_at timestamptz NULL,
            committed_client_id uuid NULL,
            result jsonb NULL
                CHECK (result IS NULL OR (jsonb_typeof(result) = 'object'
                       AND octet_length(result::text) <= 16384)),
            UNIQUE (tenant_id, id),
            CHECK (discarded_at IS NULL OR committed_at IS NULL),
            CHECK ((committed_at IS NULL) = (result IS NULL)),
            CHECK ((committed_at IS NULL) = (committed_client_id IS NULL)),
            FOREIGN KEY (tenant_id, committed_client_id) REFERENCES clients (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX client_intake_drafts_by_owner ON client_intake_drafts "
        "(tenant_id, created_by, saved_at)"
    )
    tenant_table(op, "client_intake_drafts")
    op.execute("REVOKE UPDATE, DELETE ON client_intake_drafts FROM abacus_app")
    insert_columns(op, "client_intake_drafts", ("tenant_id", "created_by", "step", "payload"))
    op.execute(f"GRANT UPDATE ({', '.join(_UPDATES)}) ON client_intake_drafts TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION client_intake_drafts_final() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF OLD.committed_at IS NOT NULL OR OLD.discarded_at IS NOT NULL THEN
                RAISE EXCEPTION 'client_intake_drafts: a committed or discarded draft is final'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER client_intake_drafts_final BEFORE UPDATE ON client_intake_drafts "
        "FOR EACH ROW EXECUTE FUNCTION client_intake_drafts_final()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE client_intake_drafts")
    op.execute("DROP FUNCTION client_intake_drafts_final()")
