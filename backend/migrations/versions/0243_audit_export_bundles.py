"""Audit-log export bundles (G-02-T17; SPEC-349 AC-12, AC-13; DEC-620, DEC-621).

`audit_exports` (0192) gains what the build stores about the sealed bundle in the exports bucket:
its segment count, its size, the signing key's id as KMS `Sign` returned it (beside the alias in
`signature_key_ref`) and, for a failed build, the failure code. The app may update them. A guard
trigger keeps the job's status moving forward only (requested to ready or failed, ready to
downloaded): a job is never re-opened, and only the system builds or fails one. What the build
wrote (the bundle's keys, digest, size, signer and expiry) changes only as the system's build
stamps it from `requested` or `building`; afterwards it is fixed.

Revision ID: 0243
Revises: 0242
"""

from __future__ import annotations

from alembic import op

revision = "0243"
down_revision = "0242"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE audit_exports
            ADD COLUMN segment_count integer NULL CHECK (segment_count >= 0),
            ADD COLUMN bundle_bytes bigint NULL CHECK (bundle_bytes >= 0),
            ADD COLUMN failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{1,63}$'),
            ADD COLUMN signature_key_id text NULL
                CHECK (char_length(signature_key_id) BETWEEN 1 AND 2048)
        """
    )
    op.execute(
        "GRANT UPDATE (segment_count, bundle_bytes, failure_code, signature_key_id) "
        "ON audit_exports TO abacus_app"
    )
    op.execute(
        """
        CREATE FUNCTION audit_exports_forward() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF current_user <> 'abacus_app' THEN
                RETURN NEW;  -- the owner's maintenance; the app is held to the rules below
            END IF;
            -- The build's stamp is written once, by the system, as it leaves requested/building.
            IF (NEW.manifest_sha256, NEW.expires_at, NEW.segment_count, NEW.csv_key,
                NEW.manifest_key, NEW.bundle_bytes, NEW.signature_key_ref, NEW.signature_key_id,
                NEW.seq_from, NEW.seq_to, NEW.row_count)
               IS DISTINCT FROM
               (OLD.manifest_sha256, OLD.expires_at, OLD.segment_count, OLD.csv_key,
                OLD.manifest_key, OLD.bundle_bytes, OLD.signature_key_ref, OLD.signature_key_id,
                OLD.seq_from, OLD.seq_to, OLD.row_count)
               AND NOT (OLD.status IN ('requested', 'building')
                        AND current_setting('app.actor_kind', true) = 'system') THEN
                RAISE EXCEPTION 'an audit export''s bundle is stamped once, by its build'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;
            IF (OLD.status IN ('requested', 'building')
                    AND NEW.status IN ('building', 'ready', 'failed')
                    AND current_setting('app.actor_kind', true) = 'system')
               OR (OLD.status = 'ready' AND NEW.status = 'downloaded'
                    AND current_setting('app.actor_kind', true) = 'human'
                    AND OLD.requested_by::text = current_setting('app.actor_id', true))
               OR (OLD.status IN ('ready', 'downloaded') AND NEW.status = 'expired'
                    AND current_setting('app.actor_kind', true) = 'system') THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'an audit export moves forward only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_exports_forward BEFORE UPDATE ON audit_exports "
        "FOR EACH ROW EXECUTE FUNCTION audit_exports_forward()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_exports_forward ON audit_exports")
    op.execute("DROP FUNCTION audit_exports_forward()")
    op.execute(
        "REVOKE UPDATE (segment_count, bundle_bytes, failure_code, signature_key_id) "
        "ON audit_exports FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE audit_exports DROP COLUMN signature_key_id, DROP COLUMN failure_code, "
        "DROP COLUMN bundle_bytes, "
        "DROP COLUMN segment_count"
    )
