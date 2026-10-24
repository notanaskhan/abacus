"""Detached-key storage for client-channel uploads and the withdrawal record (P-06-T18, T19;
ADR-162 §2, §4, §5; DEC-297).

- `evidence_versions.storage_mode` (`content_addressed` default, `detached_key`): a detached-key
  version's object is its own (`tenants/<tenant>/v/<version>`), never shared by deduplication.
  Written once, at insert, like every column of the immutable table.
- `evidence_object_keys` (tenant, forced RLS): a detached-key version's data key wrapped by the
  tenant's key, outside the object. The app inserts it with its version and may only stamp
  `retained_at`; a trigger keeps retention one-way and a retained or destroyed key unchanged.
  Acceptance retains the key (`review_decisions_retain_key`, after an `accept` insert), and an
  accept of a withdrawn version is refused there, under the key row's lock, so whichever of
  withdraw and accept commits first wins. Only `evidence_key_destroy` clears `wrapped_key` and
  stamps `destroyed_at`, from the withdrawal purge's system session, for a withdrawn, never
  retained key.
- `evidence_withdrawals` (tenant, forced RLS): one row per withdrawn version, by the session's
  own person, only for a detached-key version never accepted. Insert-only but for the purge's
  stamps: `erased_at` once, `erase_blocked_at` and `block_reason` on each blocked attempt.

Revision ID: 0144
Revises: 0143
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0144"
down_revision = "0143"
branch_labels = None
depends_on = None

# The withdrawal purge's system actor (`evidence.withdrawals.PURGE_ACTOR`), written inline below.


def upgrade() -> None:
    op.execute(
        "ALTER TABLE evidence_versions ADD COLUMN storage_mode text NOT NULL "
        "DEFAULT 'content_addressed' "
        "CHECK (storage_mode IN ('content_addressed', 'detached_key'))"
    )
    # 0007's content-address rule now holds for content-addressed versions; a detached-key
    # version's object is its own path.
    op.execute(
        "ALTER TABLE evidence_versions DROP CONSTRAINT evidence_versions_key_is_content_address"
    )
    op.execute(
        "ALTER TABLE evidence_versions ADD CONSTRAINT evidence_versions_key_is_content_address "
        "CHECK (CASE storage_mode "
        "WHEN 'content_addressed' "
        "THEN storage_key = 'tenants/' || tenant_id::text || '/sha256/' || fingerprint "
        "ELSE storage_key = 'tenants/' || tenant_id::text || '/v/' || id::text END)"
    )
    op.execute("GRANT INSERT (storage_mode) ON evidence_versions TO abacus_app")

    op.execute(
        """
        CREATE TABLE evidence_object_keys (
            tenant_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            key_id text NOT NULL CHECK (length(key_id) BETWEEN 1 AND 300),
            wrapped_key bytea NULL CHECK (length(wrapped_key) BETWEEN 16 AND 4096),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            retained_at timestamptz NULL,
            destroyed_at timestamptz NULL,
            PRIMARY KEY (tenant_id, evidence_version_id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            CONSTRAINT evidence_object_keys_destroyed CHECK (
                (wrapped_key IS NULL) = (destroyed_at IS NOT NULL)
            ),
            CONSTRAINT evidence_object_keys_retained_or_destroyed CHECK (
                retained_at IS NULL OR destroyed_at IS NULL
            )
        )
        """
    )
    tenant_table(op, "evidence_object_keys")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON evidence_object_keys FROM abacus_app")
    insert_columns(
        op, "evidence_object_keys", ("tenant_id", "evidence_version_id", "key_id", "wrapped_key")
    )
    op.execute("GRANT UPDATE (retained_at) ON evidence_object_keys TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION evidence_object_keys_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.evidence_version_id IS DISTINCT FROM OLD.evidence_version_id
               OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.key_id IS DISTINCT FROM OLD.key_id
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'a detached key''s identity never changes (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.retained_at IS NOT NULL AND (
                NEW.retained_at IS DISTINCT FROM OLD.retained_at
                OR NEW.wrapped_key IS DISTINCT FROM OLD.wrapped_key
            ) THEN
                RAISE EXCEPTION 'a retained key is never cleared (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.destroyed_at IS NOT NULL AND (
                NEW.destroyed_at IS DISTINCT FROM OLD.destroyed_at
                OR NEW.wrapped_key IS NOT NULL
                OR NEW.retained_at IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'a destroyed key stays destroyed (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER evidence_object_keys_guard BEFORE UPDATE ON evidence_object_keys "
        "FOR EACH ROW EXECUTE FUNCTION evidence_object_keys_guard()"
    )

    op.execute(
        """
        CREATE TABLE evidence_withdrawals (
            tenant_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_item_id uuid NULL,
            withdrawn_by_user_id uuid NOT NULL,
            withdrawn_at timestamptz NOT NULL,
            erase_after timestamptz NOT NULL,
            erased_at timestamptz NULL,
            erase_blocked_at timestamptz NULL,
            block_reason text NULL CHECK (block_reason ~ '^[a-z][a-z_]{0,39}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, evidence_version_id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id),
            CONSTRAINT evidence_withdrawals_window CHECK (erase_after > withdrawn_at)
        )
        """
    )
    op.execute(
        "CREATE INDEX evidence_withdrawals_pending ON evidence_withdrawals "
        "(tenant_id, erase_after) WHERE erased_at IS NULL"
    )
    tenant_table(op, "evidence_withdrawals")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON evidence_withdrawals FROM abacus_app")
    insert_columns(
        op,
        "evidence_withdrawals",
        (
            "tenant_id",
            "evidence_version_id",
            "engagement_id",
            "request_item_id",
            "withdrawn_by_user_id",
            "withdrawn_at",
            "erase_after",
        ),
    )
    op.execute(
        "GRANT UPDATE (erased_at, erase_blocked_at, block_reason) "
        "ON evidence_withdrawals TO abacus_app"
    )
    # Insert: the session's own person, a detached-key version never accepted (ADR-162 §1, §2,
    # §8). The key row is locked first, so an accept racing it waits and then sees this row.
    op.execute(
        """
        CREATE FUNCTION evidence_withdrawals_insert_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            v_mode text;
            v_retained timestamptz;
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.withdrawn_by_user_id::text
                  IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'a withdrawal is the session''s own person''s (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT storage_mode INTO v_mode FROM evidence_versions
             WHERE tenant_id = NEW.tenant_id AND id = NEW.evidence_version_id;
            SELECT retained_at INTO v_retained FROM evidence_object_keys
             WHERE tenant_id = NEW.tenant_id AND evidence_version_id = NEW.evidence_version_id
             FOR UPDATE;
            IF v_mode IS DISTINCT FROM 'detached_key' OR NOT FOUND THEN
                RAISE EXCEPTION 'only a detached-key version can be withdrawn (ADR-162)'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF v_retained IS NOT NULL OR EXISTS (
                SELECT 1 FROM review_decisions
                 WHERE tenant_id = NEW.tenant_id
                   AND evidence_version_id = NEW.evidence_version_id
                   AND decision = 'accept'
            ) THEN
                RAISE EXCEPTION 'evidence_accepted: accepted evidence is never withdrawn'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER evidence_withdrawals_insert_guard BEFORE INSERT ON evidence_withdrawals "
        "FOR EACH ROW EXECUTE FUNCTION evidence_withdrawals_insert_guard()"
    )
    op.execute(
        """
        CREATE FUNCTION evidence_withdrawals_stamp_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF (NEW.tenant_id, NEW.evidence_version_id, NEW.engagement_id, NEW.request_item_id,
                NEW.withdrawn_by_user_id, NEW.withdrawn_at, NEW.erase_after, NEW.created_at)
               IS DISTINCT FROM
               (OLD.tenant_id, OLD.evidence_version_id, OLD.engagement_id, OLD.request_item_id,
                OLD.withdrawn_by_user_id, OLD.withdrawn_at, OLD.erase_after, OLD.created_at) THEN
                RAISE EXCEPTION 'a withdrawal is insert-only but for its stamps (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.erased_at IS NOT NULL AND (
                NEW.erased_at IS DISTINCT FROM OLD.erased_at
                OR NEW.erase_blocked_at IS DISTINCT FROM OLD.erase_blocked_at
                OR NEW.block_reason IS DISTINCT FROM OLD.block_reason
            ) THEN
                RAISE EXCEPTION 'an erased withdrawal is final (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'system'
               OR current_setting('app.actor_id', true)
                  IS DISTINCT FROM 'evidence.withdrawal_purge' THEN
                RAISE EXCEPTION 'only the withdrawal purge stamps a withdrawal (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER evidence_withdrawals_stamp_guard BEFORE UPDATE ON evidence_withdrawals "
        "FOR EACH ROW EXECUTE FUNCTION evidence_withdrawals_stamp_guard()"
    )

    # Acceptance retains the key, one-way (ADR-162 §2); an accept of a withdrawn version is
    # refused after the key row's lock is taken, so a racing withdrawal decides first or loses.
    op.execute(
        """
        CREATE FUNCTION review_decisions_retain_key() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.decision <> 'accept' THEN
                RETURN NEW;
            END IF;
            UPDATE evidence_object_keys SET retained_at = clock_timestamp()
             WHERE tenant_id = NEW.tenant_id AND evidence_version_id = NEW.evidence_version_id
               AND retained_at IS NULL;
            IF EXISTS (
                SELECT 1 FROM evidence_withdrawals
                 WHERE tenant_id = NEW.tenant_id
                   AND evidence_version_id = NEW.evidence_version_id
            ) THEN
                RAISE EXCEPTION 'evidence_withdrawn: a withdrawn version is never accepted'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER review_decisions_retain_key AFTER INSERT ON review_decisions "
        "FOR EACH ROW EXECUTE FUNCTION review_decisions_retain_key()"
    )

    # Erasing seals the trust kit's content columns of the version (DEC-299): the update guard of
    # `pii_regions` and `citations` stands aside only for the table owner (the erase definer)
    # while `abacus.erasing` is on; deletes and every other table stay refused as in 0109.
    for table in _SEALABLE:
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION trust_kit_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_immutable_update BEFORE UPDATE ON {table} FOR EACH ROW "
            f"WHEN ({_NOT_ERASING}) EXECUTE FUNCTION trust_kit_immutable()"
        )
    # The crypto-erase (ADR-162 §5, §7; DEC-299): from the purge's system session only, for a
    # withdrawn version past its window that no hold covers, under the lock a hold placement
    # takes (its `hold_objects` insert holds KEY SHARE on the version row: FOR UPDATE waits for
    # it, and a later placement waits for the erase). Then everything derived from the content
    # goes too; the audit trail keeps only that the erase happened. Answers `destroyed`, `gone`
    # (already destroyed), `not_due` or `held`; nothing changes unless `destroyed`.
    op.execute(
        """
        CREATE FUNCTION evidence_key_destroy(p_version_id uuid) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
            v_withdrawal public.evidence_withdrawals%ROWTYPE;
            v_client uuid;
        BEGIN
            IF v_tenant IS NULL
               OR current_setting('app.actor_kind', true) IS DISTINCT FROM 'system'
               OR current_setting('app.actor_id', true)
                  IS DISTINCT FROM 'evidence.withdrawal_purge' THEN
                RAISE EXCEPTION 'only the withdrawal purge destroys a key (ADR-162)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT * INTO v_withdrawal FROM public.evidence_withdrawals
             WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'only a withdrawn version''s key is destroyed (ADR-162)'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF v_withdrawal.erase_after > public.abacus_now() THEN
                RETURN 'not_due';
            END IF;
            PERFORM 1 FROM public.evidence_versions
             WHERE tenant_id = v_tenant AND id = p_version_id FOR UPDATE;
            SELECT client_id INTO v_client FROM public.engagements
             WHERE tenant_id = v_tenant AND id = v_withdrawal.engagement_id;
            IF EXISTS (
                SELECT 1 FROM public.hold_objects
                 WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id
                   AND released_at IS NULL
            ) OR EXISTS (
                -- An open hold over the engagement or its client (a tax-year scope counts:
                -- fail closed rather than read the year here).
                SELECT 1 FROM public.legal_holds h
                 WHERE h.tenant_id = v_tenant AND h.status IN ('applying', 'active')
                   AND (h.engagement_id = v_withdrawal.engagement_id
                        OR (h.scope_kind NOT IN ('engagement', 'work_item')
                            AND h.client_id = v_client))
            ) THEN
                RETURN 'held';
            END IF;
            UPDATE public.evidence_object_keys
               SET wrapped_key = NULL, destroyed_at = clock_timestamp()
             WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id
               AND retained_at IS NULL AND destroyed_at IS NULL;
            IF NOT FOUND THEN
                RETURN 'gone';
            END IF;
            -- Derived records (ADR-162 §6, DEC-299): rebuilt from nothing, so deleted or sealed.
            DELETE FROM public.upload_preview_pages p USING public.upload_previews v
             WHERE p.tenant_id = v_tenant AND v.tenant_id = v_tenant AND p.preview_id = v.id
               AND v.evidence_version_id = p_version_id;
            DELETE FROM public.upload_previews
             WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id;
            DELETE FROM public.upload_checks
             WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id;
            DELETE FROM public.upload_extractions
             WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id;
            DELETE FROM public.statement_transactions t USING public.statement_datasets d
             WHERE t.tenant_id = v_tenant AND d.tenant_id = v_tenant AND t.dataset_id = d.id
               AND d.evidence_version_id = p_version_id;
            DELETE FROM public.statement_datasets
             WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id;
            UPDATE public.screening_results
               SET rationale = 'erased', citations = '[]'::jsonb, unverified = '[]'::jsonb
             WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id;
            UPDATE public.upload_review_flags f
               SET rationale = 'erased', citations = '[]'::jsonb
              FROM public.upload_reviews r
             WHERE f.tenant_id = v_tenant AND r.tenant_id = v_tenant AND f.review_id = r.id
               AND r.evidence_version_id = p_version_id;
            PERFORM set_config('abacus.erasing', 'on', true);
            UPDATE public.pii_regions SET last4 = NULL, value_sealed = ''::bytea
             WHERE tenant_id = v_tenant AND evidence_version_id = p_version_id;
            UPDATE public.citations SET value_text = NULL, quote_sha256 = NULL
             WHERE tenant_id = v_tenant AND source_type = 'evidence_version'
               AND source_id = p_version_id;
            PERFORM set_config('abacus.erasing', '', true);
            RETURN 'destroyed';
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION evidence_key_destroy(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION evidence_key_destroy(uuid) TO abacus_app")


_SEALABLE = ("pii_regions", "citations")
_NOT_ERASING = (
    "NOT (current_setting('abacus.erasing', true) = 'on' AND current_user = 'abacus_owner')"
)


def downgrade() -> None:
    # A detached-key version can't be opened without its key row: refuse rather than lose it.
    # The owner reads every tenant's rows only while the table is not forced (this transaction).
    op.execute("ALTER TABLE evidence_versions NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM evidence_versions WHERE storage_mode = 'detached_key') THEN
                RAISE EXCEPTION 'detached-key versions exist: their keys would be lost';
            END IF;
        END $$
        """
    )
    op.execute("ALTER TABLE evidence_versions FORCE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION evidence_key_destroy(uuid)")
    for table in _SEALABLE:  # 0109's single guard
        op.execute(f"DROP TRIGGER {table}_immutable_update ON {table}")
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION trust_kit_immutable()"
        )
    op.execute("DROP TRIGGER review_decisions_retain_key ON review_decisions")
    op.execute("DROP FUNCTION review_decisions_retain_key()")
    op.execute("DROP TABLE evidence_withdrawals")
    op.execute("DROP FUNCTION evidence_withdrawals_stamp_guard()")
    op.execute("DROP FUNCTION evidence_withdrawals_insert_guard()")
    op.execute("DROP TABLE evidence_object_keys")
    op.execute("DROP FUNCTION evidence_object_keys_guard()")
    op.execute("REVOKE INSERT (storage_mode) ON evidence_versions FROM abacus_app")
    op.execute(
        "ALTER TABLE evidence_versions DROP CONSTRAINT evidence_versions_key_is_content_address"
    )
    op.execute(
        "ALTER TABLE evidence_versions ADD CONSTRAINT evidence_versions_key_is_content_address "
        "CHECK (storage_key = 'tenants/' || tenant_id::text || '/sha256/' || fingerprint)"
    )
    op.execute("ALTER TABLE evidence_versions DROP COLUMN storage_mode")
