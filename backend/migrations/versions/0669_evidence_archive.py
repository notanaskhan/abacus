"""A-07 M3: the evidence archive (A-07-T09; A-07 §4.2 M3; AUD-25; DEC-2303; expand-only).

0077's `archives` (one engagement-scoped, insert-only record with a Merkle seal) gains the
work-item columns, and a v2 row assembles before it locks: it opens `assembling`, with no seal, and
the status moves to `locked` with the seal and the manifest. 0077's rows stay as they were (no
work item) and stay frozen: a trigger refuses UPDATE or DELETE on a row without a work item.

- `release_date` is the firm-local date of release, written by the service, and
  `documentation_completion_date` is **generated** as `release_date + 60` (AU-C 230), so it never
  depends on the session's time zone. `retention_until` is at least five years after release
  (I-RETENTION-FLOOR).
- Insert-only `archive_binder_indexes`, `archive_manifests` and `archive_additions`; human-only
  `archive_lock_decisions` (with the assembly attestation) and `archive_addition_decisions`, each
  bound to the transaction's actor.
- A partial index on `work_items.archive_locked_at`, for M4's guard.

Revision ID: 0669
Revises: 0668
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0669"
down_revision = "0668"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_SHA = "~ '^[0-9a-f]{64}$'"
_CREATED = "created_at timestamptz NOT NULL DEFAULT clock_timestamp()"
_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
_HUMAN = (
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
_ARCHIVE_0077 = ("tenant_id", "engagement_id", "seal", "leaf_count", "manifest", "locked_by",
                 "actor_kind")  # fmt: skip
_ARCHIVE_V2 = (
    "work_item_id", "release_id", "released_at", "release_date", "retention_policy_id",
    "retention_until", "status", "locked_at", "lock_decision_id", "manifest_id", "seal_sha256",
    "records_object_key", "records_version_id", "gate_snapshot_sha256",
)  # fmt: skip
_ARCHIVE_UPDATES = (
    "status", "locked_at", "locked_by", "lock_decision_id", "manifest_id", "seal_sha256",
    "records_object_key", "records_version_id", "gate_snapshot_sha256", "retention_until",
)  # fmt: skip
_TABLES = (
    "archive_binder_indexes",
    "archive_lock_decisions",
    "archive_manifests",
    "archive_additions",
    "archive_addition_decisions",
)
_SCOPED = ("tenant_id", "engagement_id", "work_item_id")
INSERTS: dict[str, tuple[str, ...]] = {
    "archive_binder_indexes": (
        *_SCOPED, "archive_id", "index_version", "sections", "sha256", "built_by_kind", "run_id",
    ),
    "archive_lock_decisions": (
        *_SCOPED, "archive_id", "decided_by", "assembly_complete_attested", "then_roll_forward",
        "checklist_snapshot", "checklist_sha256", "mfa_verified_at", "approval_grant_id",
        "actor_kind", "actor_id",
    ),
    "archive_manifests": (
        *_SCOPED, "archive_id", "manifest_version", "canonicalization", "evidence_leaf_count",
        "row_leaf_count", "run_record_count", "audit_checkpoint_seq_to", "audit_checkpoint_root",
        "merkle_root", "manifest_sha256", "records_object_key", "records_version_id",
        "compliance_retain_until",
    ),
    "archive_additions": (
        *_SCOPED, "archive_id", "description_sealed", "reason_code", "evidence_version_id",
        "content_sha256", "added_by", "post_issuance_event_id", "addition_manifest_key",
    ),
    "archive_addition_decisions": (
        *_SCOPED, "addition_id", "decision", "decided_by", "reason_sealed", "mfa_verified_at",
        "actor_kind", "actor_id",
    ),
}  # fmt: skip
_FROZEN_V1 = """
    CREATE FUNCTION archives_v1_frozen() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'archives are never deleted'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF OLD.work_item_id IS NULL OR OLD.status = 'locked' THEN
            RAISE EXCEPTION 'a locked archive never changes'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
"""


def _extend_archives() -> None:
    op.execute(
        f"""
        ALTER TABLE archives
            ADD COLUMN work_item_id uuid NULL,
            ADD COLUMN release_id uuid NULL,
            ADD COLUMN released_at timestamptz NULL,
            ADD COLUMN release_date date NULL,
            ADD COLUMN documentation_completion_date date
                GENERATED ALWAYS AS (release_date + 60) STORED,
            ADD COLUMN retention_policy_id uuid NULL,
            ADD COLUMN retention_until date NULL,
            ADD COLUMN status text NULL
                CHECK (status IN ('assembling', 'locking', 'locked')),
            ADD COLUMN locked_at timestamptz NULL,
            ADD COLUMN lock_decision_id uuid NULL,
            ADD COLUMN manifest_id uuid NULL,
            ADD COLUMN seal_sha256 text NULL CHECK (seal_sha256 {_SHA}),
            ADD COLUMN records_object_key text NULL
                CHECK (char_length(records_object_key) <= 1024),
            ADD COLUMN records_version_id text NULL CHECK (char_length(records_version_id) <= 256),
            ADD COLUMN gate_snapshot_sha256 text NULL CHECK (gate_snapshot_sha256 {_SHA}),
            ALTER COLUMN seal DROP NOT NULL,
            ALTER COLUMN leaf_count DROP NOT NULL,
            ALTER COLUMN manifest DROP NOT NULL,
            ALTER COLUMN locked_by DROP NOT NULL,
            ALTER COLUMN actor_kind DROP NOT NULL
        """
    )
    op.execute(
        "ALTER TABLE archives DROP CONSTRAINT archives_tenant_id_engagement_id_key, "
        "ADD CONSTRAINT archives_tenant_id_id_key UNIQUE (tenant_id, id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX archives_v1_engagement ON archives (tenant_id, engagement_id) "
        "WHERE work_item_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX archives_v2_work_item ON archives (tenant_id, work_item_id) "
        "WHERE work_item_id IS NOT NULL"
    )
    op.execute(
        """
        ALTER TABLE archives
            ADD CONSTRAINT archives_work_item FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            ADD CONSTRAINT archives_release FOREIGN KEY (tenant_id, release_id)
                REFERENCES report_releases (tenant_id, id),
            ADD CONSTRAINT archives_v1_complete CHECK (work_item_id IS NOT NULL
                OR (seal IS NOT NULL AND leaf_count IS NOT NULL AND manifest IS NOT NULL
                    AND locked_by IS NOT NULL AND actor_kind IS NOT NULL)),
            ADD CONSTRAINT archives_v2_complete CHECK (work_item_id IS NULL
                OR (release_id IS NOT NULL AND released_at IS NOT NULL
                    AND release_date IS NOT NULL AND retention_until IS NOT NULL
                    AND status IS NOT NULL)),
            ADD CONSTRAINT archives_retention_floor CHECK (retention_until IS NULL
                OR retention_until >= (release_date + interval '5 years')::date),
            ADD CONSTRAINT archives_locked_is_sealed CHECK (status IS DISTINCT FROM 'locked'
                OR (locked_at IS NOT NULL AND locked_by IS NOT NULL
                    AND lock_decision_id IS NOT NULL AND manifest_id IS NOT NULL
                    AND seal_sha256 IS NOT NULL))
        """
    )
    insert_columns(op, "archives", (*_ARCHIVE_0077, *_ARCHIVE_V2))
    op.execute(f"GRANT UPDATE ({', '.join(_ARCHIVE_UPDATES)}) ON archives TO abacus_app")
    op.execute(_FROZEN_V1)
    op.execute("REVOKE ALL ON FUNCTION archives_v1_frozen() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER archives_v1_frozen BEFORE UPDATE OR DELETE ON archives "
        "FOR EACH ROW EXECUTE FUNCTION archives_v1_frozen()"
    )


def _create_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE archive_binder_indexes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            archive_id uuid NOT NULL,
            index_version integer NOT NULL CHECK (index_version >= 1),
            sections jsonb NOT NULL CHECK (jsonb_typeof(sections) = 'array'),
            sha256 text NOT NULL CHECK (sha256 {_SHA}),
            built_by_kind text NOT NULL CHECK (built_by_kind IN ('code', 'human')),
            run_id uuid NULL,
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, archive_id, index_version),
            FOREIGN KEY (tenant_id, archive_id) REFERENCES archives (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE archive_lock_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            archive_id uuid NOT NULL,
            decided_by uuid NOT NULL,
            assembly_complete_attested boolean NOT NULL CHECK (assembly_complete_attested),
            then_roll_forward boolean NOT NULL DEFAULT false,
            checklist_snapshot jsonb NOT NULL CHECK (jsonb_typeof(checklist_snapshot) = 'array'),
            checklist_sha256 text NOT NULL CHECK (checklist_sha256 {_SHA}),
            mfa_verified_at timestamptz NOT NULL,
            approval_grant_id uuid NULL,
            {_ACTOR},
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, archive_id),
            CONSTRAINT archive_lock_decisions_by_a_person {_HUMAN},
            FOREIGN KEY (tenant_id, archive_id) REFERENCES archives (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE archive_manifests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            archive_id uuid NOT NULL,
            manifest_version integer NOT NULL CHECK (manifest_version >= 1),
            canonicalization text NOT NULL DEFAULT 'rfc8785'
                CHECK (canonicalization = 'rfc8785'),
            evidence_leaf_count integer NOT NULL CHECK (evidence_leaf_count >= 0),
            row_leaf_count integer NOT NULL CHECK (row_leaf_count >= 0),
            run_record_count integer NOT NULL CHECK (run_record_count >= 0),
            audit_checkpoint_seq_to bigint NULL,
            audit_checkpoint_root text NULL CHECK (audit_checkpoint_root {_SHA}),
            merkle_root text NOT NULL CHECK (merkle_root {_SHA}),
            manifest_sha256 text NOT NULL CHECK (manifest_sha256 {_SHA}),
            records_object_key text NULL CHECK (char_length(records_object_key) <= 1024),
            records_version_id text NULL CHECK (char_length(records_version_id) <= 256),
            compliance_retain_until date NULL,
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, archive_id, manifest_version),
            FOREIGN KEY (tenant_id, archive_id) REFERENCES archives (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE archive_additions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            archive_id uuid NOT NULL,
            description_sealed bytea NOT NULL CHECK (octet_length(description_sealed) <= 65536),
            reason_code text NOT NULL CHECK (reason_code IN ('au_c_585_omitted_procedure',
                'au_c_560_subsequently_discovered_fact', 'other')),
            evidence_version_id uuid NOT NULL,
            content_sha256 text NOT NULL CHECK (content_sha256 {_SHA}),
            added_by uuid NOT NULL,
            post_issuance_event_id uuid NULL,
            addition_manifest_key text NULL CHECK (char_length(addition_manifest_key) <= 1024),
            {_CREATED},
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, archive_id) REFERENCES archives (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE archive_addition_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            addition_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('approved', 'rejected')),
            decided_by uuid NOT NULL,
            reason_sealed bytea NULL CHECK (octet_length(reason_sealed) <= 65536),
            mfa_verified_at timestamptz NOT NULL,
            {_ACTOR},
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, addition_id),
            CONSTRAINT archive_addition_decisions_by_a_person {_HUMAN},
            FOREIGN KEY (tenant_id, addition_id)
                REFERENCES archive_additions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )


def upgrade() -> None:
    _extend_archives()
    _create_tables()
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERTS[table])
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION a07_rows_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION a07_rows_immutable()"
        )
    op.execute(
        "ALTER TABLE archives ADD CONSTRAINT archives_lock_decision "
        "FOREIGN KEY (tenant_id, lock_decision_id) REFERENCES archive_lock_decisions "
        "(tenant_id, id), ADD CONSTRAINT archives_manifest "
        "FOREIGN KEY (tenant_id, manifest_id) REFERENCES archive_manifests (tenant_id, id)"
    )
    op.execute(
        "CREATE INDEX work_items_archive_locked ON work_items (tenant_id, id) "
        "WHERE archive_locked_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX work_items_archive_locked")
    op.execute(
        "ALTER TABLE archives DROP CONSTRAINT archives_lock_decision, "
        "DROP CONSTRAINT archives_manifest"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP TRIGGER archives_v1_frozen ON archives")
    op.execute("DROP FUNCTION archives_v1_frozen()")
    op.execute(f"REVOKE UPDATE ({', '.join(_ARCHIVE_UPDATES)}) ON archives FROM abacus_app")
    op.execute("DELETE FROM archives WHERE work_item_id IS NOT NULL")
    op.execute("DROP INDEX archives_v2_work_item")
    op.execute("DROP INDEX archives_v1_engagement")
    op.execute(
        "ALTER TABLE archives "
        "DROP CONSTRAINT archives_locked_is_sealed, DROP CONSTRAINT archives_retention_floor, "
        "DROP CONSTRAINT archives_v2_complete, DROP CONSTRAINT archives_v1_complete, "
        "DROP CONSTRAINT archives_release, DROP CONSTRAINT archives_work_item, "
        "DROP CONSTRAINT archives_tenant_id_id_key, "
        "ADD CONSTRAINT archives_tenant_id_engagement_id_key UNIQUE (tenant_id, engagement_id), "
        + ", ".join(
            f"DROP COLUMN {c}" for c in ("documentation_completion_date", *reversed(_ARCHIVE_V2))
        )
        + ", ALTER COLUMN seal SET NOT NULL, ALTER COLUMN leaf_count SET NOT NULL, "
        "ALTER COLUMN manifest SET NOT NULL, ALTER COLUMN locked_by SET NOT NULL, "
        "ALTER COLUMN actor_kind SET NOT NULL"
    )
    insert_columns(op, "archives", _ARCHIVE_0077)
