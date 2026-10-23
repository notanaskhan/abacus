"""Legal holds and reference-counted hold objects (Q-02-T29; Q-02 §4.2, AC-34 to AC-37; DEC-71 /
P-14, ADR-033; DEC-228).

- `legal_holds` (tenant, forced RLS): a person's hold on a client, a client and tax year, an
  engagement or a work item, with a reason code and the people to notify. `client_id` is always
  set (resolved at placement) so walls and lists filter on it. Status moves forward only:
  `applying` -> `active` -> `releasing` -> `released`. `placed_by` and `released_by` are bound to
  the session's human actor (the 0015 pattern): an agent or the platform can't place or lift one.
  The app may update only the status columns; nothing is deleted.
- `hold_objects` (tenant, forced RLS): one row per evidence version a hold covers, the reference
  count. Rows are written in the placing transaction and on every new version in scope, before
  any S3 call, so the database counts a hold before S3 catches up (Q-02 R12). `applied_at` is
  stamped once the S3 legal hold is set; `released_at` when the hold lets go of it. The S3 hold
  comes off an object only when no unreleased row names that stored object.
- `active_hold_count(evidence_version_id)`: how many holds still cover a version (invoker rights,
  so row-level security answers for the transaction's firm only).

Revision ID: 0126
Revises: 0125
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0126"
down_revision = "0125"
branch_labels = None
depends_on = None

_SCOPES = "('client', 'client_tax_year', 'engagement', 'work_item')"
_REASONS = "('irs_examination', 'litigation', 'regulatory_inquiry', 'subpoena', 'other')"
_STATUSES = "('applying', 'active', 'releasing', 'released')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE legal_holds (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            scope_kind text NOT NULL CHECK (scope_kind IN {_SCOPES}),
            client_id uuid NOT NULL,
            tax_year smallint NULL CHECK (tax_year BETWEEN 1990 AND 2100),
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            reason_code text NOT NULL CHECK (reason_code IN {_REASONS}),
            details text NULL CHECK (char_length(details) BETWEEN 1 AND 2000),
            notify_user_ids uuid[] NOT NULL DEFAULT '{{}}'
                CHECK (cardinality(notify_user_ids) <= 50),
            placed_by uuid NOT NULL,
            placed_at timestamptz NOT NULL DEFAULT abacus_now(),
            status text NOT NULL DEFAULT 'applying' CHECK (status IN {_STATUSES}),
            applied_at timestamptz NULL,
            released_by uuid NULL,
            released_at timestamptz NULL,
            release_reason text NULL CHECK (char_length(release_reason) BETWEEN 1 AND 500),
            UNIQUE (tenant_id, id),
            CONSTRAINT legal_holds_scope_shape CHECK (
                CASE scope_kind
                    WHEN 'client' THEN tax_year IS NULL AND engagement_id IS NULL
                        AND work_item_id IS NULL
                    WHEN 'client_tax_year' THEN tax_year IS NOT NULL AND engagement_id IS NULL
                        AND work_item_id IS NULL
                    WHEN 'engagement' THEN tax_year IS NULL AND engagement_id IS NOT NULL
                        AND work_item_id IS NULL
                    ELSE tax_year IS NULL AND engagement_id IS NOT NULL
                        AND work_item_id IS NOT NULL
                END
            ),
            CONSTRAINT legal_holds_release_shape CHECK (
                (status IN ('applying', 'active')) = (released_by IS NULL)
                AND (status = 'released') = (released_at IS NOT NULL)
            ),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX legal_holds_open ON legal_holds (tenant_id, client_id) "
        "WHERE status <> 'released'"
    )
    tenant_table(op, "legal_holds")
    op.execute("REVOKE DELETE, TRUNCATE ON legal_holds FROM abacus_app")
    insert_columns(
        op,
        "legal_holds",
        (
            "id",
            "tenant_id",
            "scope_kind",
            "client_id",
            "tax_year",
            "engagement_id",
            "work_item_id",
            "reason_code",
            "details",
            "notify_user_ids",
            "placed_by",
        ),
    )
    op.execute("REVOKE UPDATE ON legal_holds FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, applied_at, released_by, released_at, release_reason) "
        "ON legal_holds TO abacus_app"
    )
    # Forward-only status, and the person placing or lifting is the session's own human actor.
    op.execute(
        """
        CREATE FUNCTION legal_holds_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            v_rank constant text[] := ARRAY['applying', 'active', 'releasing', 'released'];
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'applying' THEN
                    RAISE EXCEPTION 'a legal hold starts applying'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                   OR NEW.placed_by::text IS DISTINCT FROM current_setting('app.actor_id', true)
                THEN
                    RAISE EXCEPTION 'a legal hold is placed by the session''s own person'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN NEW;
            END IF;
            IF array_position(v_rank, NEW.status) < array_position(v_rank, OLD.status) THEN
                RAISE EXCEPTION 'legal_hold_status_backwards'
                    USING ERRCODE = 'check_violation', CONSTRAINT = 'legal_holds_forward_only';
            END IF;
            IF NEW.released_by IS DISTINCT FROM OLD.released_by THEN
                IF OLD.released_by IS NOT NULL
                   OR current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                   OR NEW.released_by::text IS DISTINCT FROM current_setting('app.actor_id', true)
                THEN
                    RAISE EXCEPTION 'a legal hold is lifted by the session''s own person'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            END IF;
            IF OLD.release_reason IS NOT NULL
               AND NEW.release_reason IS DISTINCT FROM OLD.release_reason THEN
                RAISE EXCEPTION 'a release reason is kept as written'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER legal_holds_guard BEFORE INSERT OR UPDATE ON legal_holds "
        "FOR EACH ROW EXECUTE FUNCTION legal_holds_guard()"
    )

    op.execute(
        """
        CREATE TABLE hold_objects (
            tenant_id uuid NOT NULL,
            hold_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            object_key text NOT NULL CHECK (char_length(object_key) BETWEEN 1 AND 1024),
            object_version_id text NOT NULL
                CHECK (char_length(object_version_id) BETWEEN 1 AND 1024),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            applied_at timestamptz NULL,
            released_at timestamptz NULL,
            PRIMARY KEY (hold_id, evidence_version_id),
            FOREIGN KEY (tenant_id, hold_id) REFERENCES legal_holds (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX hold_objects_by_version ON hold_objects (tenant_id, evidence_version_id) "
        "WHERE released_at IS NULL"
    )
    op.execute(
        "CREATE INDEX hold_objects_by_object ON hold_objects "
        "(tenant_id, object_key, object_version_id) WHERE released_at IS NULL"
    )
    tenant_table(op, "hold_objects")
    op.execute("REVOKE DELETE, TRUNCATE ON hold_objects FROM abacus_app")
    insert_columns(
        op,
        "hold_objects",
        ("tenant_id", "hold_id", "evidence_version_id", "object_key", "object_version_id"),
    )
    op.execute("REVOKE UPDATE ON hold_objects FROM abacus_app")
    op.execute("GRANT UPDATE (applied_at, released_at) ON hold_objects TO abacus_app")
    # A release is final: a released row is never brought back (a new hold writes its own row).
    op.execute(
        """
        CREATE FUNCTION hold_objects_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.released_at IS NOT NULL AND NEW.released_at IS DISTINCT FROM OLD.released_at
            THEN
                RAISE EXCEPTION 'a released hold object stays released'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.applied_at IS NOT NULL AND NEW.applied_at IS DISTINCT FROM OLD.applied_at THEN
                RAISE EXCEPTION 'applied_at is stamped once' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER hold_objects_guard BEFORE UPDATE ON hold_objects "
        "FOR EACH ROW EXECUTE FUNCTION hold_objects_guard()"
    )
    op.execute(
        """
        CREATE FUNCTION active_hold_count(p_evidence_version_id uuid) RETURNS integer
        LANGUAGE sql STABLE AS $$
            SELECT count(*)::integer FROM public.hold_objects
             WHERE evidence_version_id = p_evidence_version_id AND released_at IS NULL
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION active_hold_count(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION active_hold_count(uuid) TO abacus_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION active_hold_count(uuid)")
    op.execute("DROP TABLE hold_objects")
    op.execute("DROP FUNCTION hold_objects_guard()")
    op.execute("DROP TABLE legal_holds")
    op.execute("DROP FUNCTION legal_holds_guard()")
