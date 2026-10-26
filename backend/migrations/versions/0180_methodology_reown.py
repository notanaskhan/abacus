"""K-01-T02: methodology re-owned, with a version lifecycle (K-01 §4.2 migration A; ADR-140).

The five `methodology_*` tables (0019) move to the `methodology` module's registry; their rows,
grants and insert-only rule are unchanged. This migration adds:

- `methodology_templates.family` (`ebp`, `fs` or `ssars`; null for legacy templates), set on
  insert.
- `methodology_versions.label` (backfilled `'v' || version`, then required),
  `drafted_from_version_id` (a draft's or a drafted-guidance publish's source) and `origin`
  (`workbook`, `document_import`, `draft`, `guidance_draft` or `legacy`; legacy rows read
  `legacy`), set on insert.
- `methodology_version_states` (new, mutable under guarded transitions; one row per version): the
  lifecycle status, effective dates, who approved (a person only), the approval basis, the
  standards set, the quality-management reference, the engagement types and whether it is the
  template's default for new engagements (at most one published default per template).
- `methodology_version_events` (new, insert-only): what happened to a version, with identifiers
  and codes only in `facts`; it feeds KNW-02's Activity and KNW-01's change log without reading
  the audit trail.
- `standards_sets` (new, global): the standards a methodology follows (GAAS nonissuer, SSARS,
  SQMS). No app privilege: rows arrive through the reference-data publish path (K-02, DEC-76),
  never a migration insert; a SECURITY DEFINER reader comes with K-01-T18. `engagements
  .standards_set_id` (0069) gains its foreign key.
- Backfill: every existing version is `published`, `approval_basis = legacy_import`, effective
  from its creation date; each template's newest version is its default; one
  `legacy_backfilled` event per version.

Revision ID: 0180
Revises: 0172
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0180"
down_revision = "0172"
branch_labels = None
depends_on = None

_LEGACY = ("methodology_templates", "methodology_versions")
_STATE_UPDATES = (
    "status",
    "effective_from",
    "effective_to",
    "approved_by",
    "approved_at",
    "approved_actor_kind",
    "approval_basis",
    "standards_set_id",
    "quality_management_ref",
    "engagement_types",
    "default_for_new_engagements",
    "row_version",
)


_APPROVER = """
    CREATE FUNCTION methodology_version_states_approver() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF TG_OP = 'UPDATE' THEN
            NEW.updated_at := abacus_now();
        END IF;
        IF (TG_OP = 'INSERT' AND (NEW.approved_by IS NOT NULL
                                  OR NEW.approved_actor_kind IS NOT NULL))
           OR (TG_OP = 'UPDATE' AND (NEW.approved_by IS DISTINCT FROM OLD.approved_by
                                     OR NEW.approved_actor_kind
                                        IS DISTINCT FROM OLD.approved_actor_kind)) THEN
            IF NEW.approved_actor_kind IS DISTINCT FROM current_setting('app.actor_kind', true)
               OR NEW.approved_by::text IS DISTINCT FROM current_setting('app.actor_id', true)
            THEN
                RAISE EXCEPTION 'a version is approved by the person acting, as themself'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
        END IF;
        RETURN NEW;
    END $$
"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE methodology_templates ADD COLUMN family text NULL "
        "CHECK (family IN ('ebp', 'fs', 'ssars'))"
    )
    op.execute("GRANT INSERT (family) ON methodology_templates TO abacus_app")
    op.execute(
        """
        ALTER TABLE methodology_versions
            ADD COLUMN label text NULL CHECK (length(label) BETWEEN 1 AND 40),
            ADD COLUMN drafted_from_version_id uuid NULL,
            ADD COLUMN origin text NOT NULL DEFAULT 'legacy'
                CHECK (origin IN ('workbook', 'document_import', 'draft', 'guidance_draft',
                                  'legacy')),
            ADD CONSTRAINT methodology_versions_drafted_from_fkey
                FOREIGN KEY (tenant_id, drafted_from_version_id)
                REFERENCES methodology_versions (tenant_id, id)
        """
    )
    # Owner reads and writes bypass row-level security only with it unforced (0172's pattern);
    # it is forced again below, inside this transaction.
    for table in _LEGACY:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("UPDATE methodology_versions SET label = 'v' || version WHERE label IS NULL")
    op.execute("ALTER TABLE methodology_versions ALTER COLUMN label SET NOT NULL")
    op.execute(
        "GRANT INSERT (label, drafted_from_version_id, origin) ON methodology_versions "
        "TO abacus_app"
    )

    op.execute(
        """
        CREATE TABLE standards_sets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code text NOT NULL UNIQUE CHECK (code ~ '^[a-z0-9][a-z0-9_.-]{0,59}$'),
            label text NOT NULL CHECK (length(btrim(label)) BETWEEN 1 AND 200),
            standard_refs text[] NOT NULL DEFAULT '{}',
            family text NOT NULL CHECK (family IN ('gaas_nonissuer', 'ssars', 'sqms')),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("REVOKE ALL ON standards_sets FROM abacus_app")
    op.execute(
        "ALTER TABLE engagements ADD CONSTRAINT engagements_standards_set_fkey "
        "FOREIGN KEY (standards_set_id) REFERENCES standards_sets (id) NOT VALID"
    )
    op.execute("ALTER TABLE engagements VALIDATE CONSTRAINT engagements_standards_set_fkey")

    op.execute(
        """
        CREATE TABLE methodology_version_states (
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            template_id uuid NOT NULL,
            status text NOT NULL CHECK (status IN ('draft', 'parsing', 'needs_review',
                                                  'published', 'superseded', 'discarded')),
            effective_from date NULL,
            effective_to date NULL,
            approved_by uuid NULL,
            approved_at timestamptz NULL,
            approved_actor_kind text NULL
                CHECK (approved_actor_kind IS NULL OR approved_actor_kind = 'human'),
            approval_basis text NULL CHECK (approval_basis IN ('approved', 'legacy_import')),
            standards_set_id uuid NULL REFERENCES standards_sets (id),
            quality_management_ref text NULL
                CHECK (length(quality_management_ref) BETWEEN 1 AND 120),
            engagement_types text[] NOT NULL DEFAULT '{}',
            default_for_new_engagements boolean NOT NULL DEFAULT false,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, version_id),
            FOREIGN KEY (tenant_id, version_id) REFERENCES methodology_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, template_id) REFERENCES methodology_templates (tenant_id, id),
            CONSTRAINT methodology_version_states_dated CHECK (
                status NOT IN ('published', 'superseded')
                OR (effective_from IS NOT NULL AND approval_basis IS NOT NULL)),
            CONSTRAINT methodology_version_states_approver CHECK (
                approval_basis IS DISTINCT FROM 'approved'
                OR (approved_by IS NOT NULL AND approved_actor_kind = 'human')),
            CONSTRAINT methodology_version_states_range CHECK (
                effective_to IS NULL OR effective_to >= effective_from)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX methodology_version_states_one_default "
        "ON methodology_version_states (tenant_id, template_id) "
        "WHERE default_for_new_engagements AND status = 'published'"
    )
    op.execute(
        """
        CREATE TABLE methodology_version_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            seq bigint GENERATED ALWAYS AS IDENTITY,
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('legacy_backfilled', 'imported', 'published',
                                                'draft_created', 'submitted', 'approved',
                                                'superseded', 'discarded', 'standards_mapped',
                                                'exported')),
            actor_user_id uuid NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind IN ('human', 'agent', 'system')),
            on_behalf_of_user_id uuid NULL,
            at timestamptz NOT NULL DEFAULT abacus_now(),
            facts jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(facts) = 'object'),
            FOREIGN KEY (tenant_id, version_id) REFERENCES methodology_versions (tenant_id, id),
            CONSTRAINT methodology_version_events_own_actor CHECK (
                actor_user_id IS NULL
                OR actor_user_id::text = current_setting('app.actor_id', true))
        )
        """
    )
    op.execute(
        "CREATE INDEX methodology_version_events_by_version "
        "ON methodology_version_events (tenant_id, version_id, seq)"
    )

    # Backfill, before row-level security: legacy versions are published on their own authority.
    op.execute(
        """
        INSERT INTO methodology_version_states (tenant_id, version_id, template_id, status,
            effective_from, approval_basis, engagement_types, default_for_new_engagements)
        SELECT v.tenant_id, v.id, v.template_id, 'published', v.created_at::date,
               'legacy_import', t.engagement_types,
               v.version = (SELECT max(w.version) FROM methodology_versions w
                            WHERE w.tenant_id = v.tenant_id AND w.template_id = v.template_id)
          FROM methodology_versions v
          JOIN methodology_templates t ON t.tenant_id = v.tenant_id AND t.id = v.template_id
        """
    )
    op.execute(
        "INSERT INTO methodology_version_events (tenant_id, version_id, kind, actor_kind, at) "
        "SELECT tenant_id, id, 'legacy_backfilled', 'system', created_at "
        "FROM methodology_versions"
    )

    for table in _LEGACY:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # Who approved is the transaction's actor, never a column the app attests (ADR-005).
    op.execute(_APPROVER)
    op.execute(
        "CREATE TRIGGER methodology_version_states_approver BEFORE INSERT OR UPDATE "
        "ON methodology_version_states FOR EACH ROW "
        "EXECUTE FUNCTION methodology_version_states_approver()"
    )
    tenant_table(op, "methodology_version_states")
    op.execute("REVOKE UPDATE, DELETE ON methodology_version_states FROM abacus_app")
    insert_columns(
        op,
        "methodology_version_states",
        ("tenant_id", "version_id", "template_id", *_STATE_UPDATES),
    )
    op.execute(
        f"GRANT UPDATE ({', '.join(_STATE_UPDATES)}) ON methodology_version_states TO abacus_app"
    )

    op.execute(
        """
        CREATE FUNCTION methodology_version_events_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'methodology_version_events is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER methodology_version_events_immutable BEFORE UPDATE OR DELETE "
        "ON methodology_version_events FOR EACH ROW "
        "EXECUTE FUNCTION methodology_version_events_immutable()"
    )
    tenant_table(op, "methodology_version_events")
    op.execute("REVOKE UPDATE, DELETE ON methodology_version_events FROM abacus_app")
    insert_columns(
        op,
        "methodology_version_events",
        ("tenant_id", "version_id", "kind", "actor_user_id", "on_behalf_of_user_id", "facts"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE methodology_version_events")
    op.execute("DROP FUNCTION methodology_version_events_immutable()")
    op.execute("DROP TABLE methodology_version_states")
    op.execute("DROP FUNCTION methodology_version_states_approver()")
    op.execute("ALTER TABLE engagements DROP CONSTRAINT engagements_standards_set_fkey")
    op.execute("DROP TABLE standards_sets")
    op.execute(
        "REVOKE INSERT (label, drafted_from_version_id, origin) ON methodology_versions "
        "FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE methodology_versions DROP CONSTRAINT methodology_versions_drafted_from_fkey, "
        "DROP COLUMN origin, DROP COLUMN drafted_from_version_id, DROP COLUMN label"
    )
    op.execute("REVOKE INSERT (family) ON methodology_templates FROM abacus_app")
    op.execute("ALTER TABLE methodology_templates DROP COLUMN family")
