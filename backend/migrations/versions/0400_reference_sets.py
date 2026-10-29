"""Global reference sets (K-02-T03; K-02 §4.2 M-A; ADR-300, P-62; SPEC-500 AC-8 to AC-10).

No rule is written here: due dates, holidays, postponements, the 8879 form set and tolerances,
thresholds, retention minimums and standards sets are content, drafted and published by two
people through the operator CLI (K-02-T06), never a migration insert (AGENTS 16).

- `reference_sets` (global): one row per set (`key`, `kind`, jurisdiction, title, content owner).
  `kind` holds the seven kinds of ADR-300 and Q-05's two reserved ones.
- `reference_set_versions` (global): immutable once published. A version is `draft`, then
  `published` only when its approver differs from its drafter (a CHECK), then possibly
  `withdrawn` by two other handles (a CHECK); a trigger freezes everything else once it leaves
  `draft` and refuses deleting a published or withdrawn version. One draft per set.
- `reference_set_publications` (global, insert-only, immutable): who published or withdrew what,
  with both handles and the reason.

The app has no grant on any of the three. Definers:
- `reference_set_resolve(key, as_of)`, `reference_set_list(kind)`, `reference_set_history(key)`:
  the app's readers, published (and, for history, withdrawn) versions only, never a draft.
- `reference_set_draft(...)`, `reference_set_publish(version, approver, reason)`,
  `reference_set_withdraw(version, operator, approver, reason)`, `active_tenant_ids()` and
  `standards_sets_apply(version)`: owner-only (the CLI's and the fan-out's), never executable by
  `abacus_app`.
- Publishing a `standards_sets` version calls `standards_sets_apply`, which inserts new codes
  into K-01's `standards_sets` (0180) and updates the label and refs of existing ones. It never
  deletes a row (`engagements.standards_set_id` references it) and refuses a version that drops
  a code or moves one to another family.

Revision ID: 0400
Revises: 0295
"""

from __future__ import annotations

from alembic import op

revision = "0400"
down_revision = "0295"
branch_labels = None
depends_on = None

_KINDS = (
    "('due_date_rules', 'legal_holidays', 'disaster_postponements', 'form_8879_set', "
    "'information_return_thresholds', 'retention_minimums', 'standards_sets', "
    "'state_breach_matrix', 'state_retention_rules')"
)
_HANDLE = "text NOT NULL CHECK (char_length({c}) BETWEEN 1 AND 200)"
_READERS = (
    "reference_set_resolve(text, date)",
    "reference_set_list(text)",
    "reference_set_history(text)",
)
_OWNER_ONLY = (
    "reference_set_draft(text, text, text, text, text, text, integer, date, jsonb, text, jsonb,"
    " text, text)",
    "reference_set_publish(uuid, text, text)",
    "reference_set_withdraw(uuid, text, text, text)",
    "active_tenant_ids()",
    "standards_sets_apply(uuid)",
)
_TRIGGER_FUNCTIONS = ("reference_set_versions_freeze()", "reference_set_publications_immutable()")


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE reference_sets (
            key text PRIMARY KEY CHECK (key ~ '^[a-z0-9_.]{{3,80}}$'),
            kind text NOT NULL CHECK (kind IN {_KINDS}),
            jurisdiction text NULL CHECK (char_length(jurisdiction) BETWEEN 1 AND 20),
            title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
            content_owner {_HANDLE.format(c="content_owner")},
            description text NULL CHECK (char_length(description) BETWEEN 1 AND 1000),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE reference_set_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            set_key text NOT NULL REFERENCES reference_sets (key),
            version integer NOT NULL CHECK (version > 0),
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'withdrawn')),
            tax_year integer NULL CHECK (tax_year BETWEEN 2000 AND 2100),
            effective_from date NOT NULL,
            payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
            payload_schema_version integer NOT NULL DEFAULT 1 CHECK (payload_schema_version > 0),
            payload_hash text NOT NULL CHECK (payload_hash ~ '^sha256:[0-9a-f]{{64}}$'),
            source_citations jsonb NOT NULL CHECK (jsonb_typeof(source_citations) = 'array'),
            drafted_by {_HANDLE.format(c="drafted_by")},
            drafted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            change_reason text NOT NULL
                CHECK (char_length(btrim(change_reason)) BETWEEN 1 AND 500),
            approved_by text NULL CHECK (char_length(approved_by) BETWEEN 1 AND 200),
            published_at timestamptz NULL,
            withdrawn_by text NULL CHECK (char_length(withdrawn_by) BETWEEN 1 AND 200),
            withdrawal_approved_by text NULL
                CHECK (char_length(withdrawal_approved_by) BETWEEN 1 AND 200),
            withdrawn_at timestamptz NULL,
            UNIQUE (set_key, version),
            -- Two people: the approver is never the drafter (ADR-300).
            CHECK (status = 'draft' OR (approved_by IS NOT NULL AND approved_by <> drafted_by
                                        AND published_at IS NOT NULL)),
            CHECK (status <> 'draft' OR (approved_by IS NULL AND published_at IS NULL)),
            CHECK ((status = 'withdrawn') = (withdrawn_at IS NOT NULL)),
            CHECK (status <> 'withdrawn' OR (withdrawn_by IS NOT NULL
                                             AND withdrawal_approved_by IS NOT NULL
                                             AND withdrawal_approved_by <> withdrawn_by))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX reference_set_versions_one_draft "
        "ON reference_set_versions (set_key) WHERE status = 'draft'"
    )
    op.execute(
        "CREATE INDEX reference_set_versions_resolve "
        "ON reference_set_versions (set_key, effective_from DESC, version DESC) "
        "WHERE status = 'published'"
    )
    op.execute(
        f"""
        CREATE TABLE reference_set_publications (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            version_id uuid NOT NULL REFERENCES reference_set_versions (id),
            action text NOT NULL CHECK (action IN ('published', 'withdrawn')),
            operator {_HANDLE.format(c="operator")},
            approver {_HANDLE.format(c="approver")},
            reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 1 AND 500),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (approver <> operator)
        )
        """
    )
    for table in ("reference_sets", "reference_set_versions", "reference_set_publications"):
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")

    # A version leaves `draft` once; after that only `published` -> `withdrawn` moves, and
    # nothing else changes. A published or withdrawn version is never deleted.
    op.execute(
        """
        CREATE FUNCTION reference_set_versions_freeze() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF TG_OP = 'TRUNCATE' THEN
                RAISE EXCEPTION 'reference_set_versions cannot be truncated'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF OLD.status <> 'draft' THEN
                    RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN OLD;
            END IF;
            IF NEW.id <> OLD.id OR NEW.set_key <> OLD.set_key OR NEW.version <> OLD.version
               OR NEW.drafted_by <> OLD.drafted_by OR NEW.drafted_at <> OLD.drafted_at THEN
                RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.status = 'draft' THEN
                RETURN NEW;
            END IF;
            IF OLD.status = 'published' AND NEW.status = 'withdrawn'
               AND NEW.tax_year IS NOT DISTINCT FROM OLD.tax_year
               AND NEW.effective_from = OLD.effective_from
               AND NEW.payload = OLD.payload
               AND NEW.payload_schema_version = OLD.payload_schema_version
               AND NEW.payload_hash = OLD.payload_hash
               AND NEW.source_citations = OLD.source_citations
               AND NEW.change_reason = OLD.change_reason
               AND NEW.approved_by = OLD.approved_by
               AND NEW.published_at = OLD.published_at THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER reference_set_versions_freeze BEFORE UPDATE OR DELETE "
        "ON reference_set_versions FOR EACH ROW EXECUTE FUNCTION reference_set_versions_freeze()"
    )
    op.execute(
        "CREATE TRIGGER reference_set_versions_no_truncate BEFORE TRUNCATE "
        "ON reference_set_versions FOR EACH STATEMENT "
        "EXECUTE FUNCTION reference_set_versions_freeze()"
    )
    op.execute(
        """
        CREATE FUNCTION reference_set_publications_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'reference_set_publications is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER reference_set_publications_immutable BEFORE UPDATE OR DELETE "
        "ON reference_set_publications FOR EACH ROW "
        "EXECUTE FUNCTION reference_set_publications_immutable()"
    )
    op.execute(
        "CREATE TRIGGER reference_set_publications_no_truncate BEFORE TRUNCATE "
        "ON reference_set_publications FOR EACH STATEMENT "
        "EXECUTE FUNCTION reference_set_publications_immutable()"
    )

    # --- the app's readers: published only, never a draft ---------------------------------------
    op.execute(
        """
        CREATE FUNCTION reference_set_resolve(p_key text, p_as_of date)
        RETURNS TABLE (version_id uuid, set_key text, kind text, version integer,
                       tax_year integer, effective_from date, payload jsonb,
                       payload_schema_version integer, payload_hash text,
                       source_citations jsonb, drafted_by text, approved_by text,
                       change_reason text, published_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT v.id, v.set_key, s.kind, v.version, v.tax_year, v.effective_from, v.payload,
                   v.payload_schema_version, v.payload_hash, v.source_citations, v.drafted_by,
                   v.approved_by, v.change_reason, v.published_at
              FROM public.reference_set_versions v
              JOIN public.reference_sets s ON s.key = v.set_key
             WHERE v.set_key = p_key AND v.status = 'published' AND v.effective_from <= p_as_of
             ORDER BY v.effective_from DESC, v.version DESC
             LIMIT 1
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION reference_set_list(p_kind text)
        RETURNS TABLE (key text, kind text, jurisdiction text, title text, content_owner text,
                       description text, current_version integer, current_effective_from date)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT s.key, s.kind, s.jurisdiction, s.title, s.content_owner, s.description,
                   c.version, c.effective_from
              FROM public.reference_sets s
              LEFT JOIN LATERAL (
                  SELECT v.version, v.effective_from
                    FROM public.reference_set_versions v
                   WHERE v.set_key = s.key AND v.status = 'published'
                     AND v.effective_from <= abacus_now()::date
                   ORDER BY v.effective_from DESC, v.version DESC
                   LIMIT 1
              ) c ON true
             WHERE (p_kind IS NULL OR s.kind = p_kind)
               AND EXISTS (SELECT 1 FROM public.reference_set_versions p
                            WHERE p.set_key = s.key AND p.status <> 'draft')
             ORDER BY s.kind, s.key
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION reference_set_history(p_key text)
        RETURNS TABLE (version_id uuid, set_key text, kind text, version integer, status text,
                       tax_year integer, effective_from date, payload jsonb,
                       payload_schema_version integer, payload_hash text,
                       source_citations jsonb, drafted_by text, approved_by text,
                       change_reason text, published_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT v.id, v.set_key, s.kind, v.version, v.status, v.tax_year, v.effective_from,
                   v.payload, v.payload_schema_version, v.payload_hash, v.source_citations,
                   v.drafted_by, v.approved_by, v.change_reason, v.published_at
              FROM public.reference_set_versions v
              JOIN public.reference_sets s ON s.key = v.set_key
             WHERE v.set_key = p_key AND v.status <> 'draft'
             ORDER BY v.version DESC
        $$
        """
    )

    # --- the operators' writers: owner-only ----------------------------------------------------
    op.execute(
        """
        CREATE FUNCTION reference_set_draft(
            p_key text, p_kind text, p_title text, p_jurisdiction text, p_content_owner text,
            p_description text, p_tax_year integer, p_effective_from date, p_payload jsonb,
            p_payload_hash text, p_citations jsonb, p_drafted_by text, p_reason text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_kind text;
            v_next integer;
            v_id uuid;
        BEGIN
            SELECT kind INTO v_kind FROM public.reference_sets WHERE key = p_key FOR UPDATE;
            IF NOT FOUND THEN
                INSERT INTO public.reference_sets (key, kind, jurisdiction, title, content_owner,
                    description)
                VALUES (p_key, p_kind, p_jurisdiction, p_title, p_content_owner, p_description);
            ELSIF v_kind <> p_kind THEN
                RAISE EXCEPTION 'kind_mismatch' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF p_payload->>'kind' IS DISTINCT FROM p_kind THEN
                RAISE EXCEPTION 'payload_kind_mismatch' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF EXISTS (SELECT 1 FROM public.reference_set_versions
                        WHERE set_key = p_key AND status = 'draft') THEN
                RAISE EXCEPTION 'draft_exists' USING ERRCODE = 'unique_violation';
            END IF;
            SELECT coalesce(max(version), 0) + 1 INTO v_next
              FROM public.reference_set_versions WHERE set_key = p_key;
            INSERT INTO public.reference_set_versions (set_key, version, tax_year, effective_from,
                payload, payload_hash, source_citations, drafted_by, change_reason)
            VALUES (p_key, v_next, p_tax_year, p_effective_from, p_payload, p_payload_hash,
                    p_citations, p_drafted_by, p_reason)
            RETURNING id INTO v_id;
            RETURN v_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION standards_sets_apply(p_version_id uuid) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_payload jsonb;
            v_kind text;
            v_rows integer;
        BEGIN
            SELECT v.payload, s.kind INTO v_payload, v_kind
              FROM public.reference_set_versions v
              JOIN public.reference_sets s ON s.key = v.set_key
             WHERE v.id = p_version_id;
            IF v_kind IS DISTINCT FROM 'standards_sets' THEN
                RAISE EXCEPTION 'not_standards_sets' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            -- Only the three nonissuer families (X-07, DEC-19); the table's CHECK agrees.
            IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_payload->'rows') r
                        WHERE r->>'family' NOT IN ('gaas_nonissuer', 'ssars', 'sqms')) THEN
                RAISE EXCEPTION 'family_not_allowed' USING ERRCODE = 'check_violation';
            END IF;
            -- A published code is never removed or moved to another family.
            IF EXISTS (SELECT 1 FROM public.standards_sets s
                        WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements(v_payload->'rows') r
                                           WHERE r->>'code' = s.code)) THEN
                RAISE EXCEPTION 'code_removed' USING ERRCODE = 'check_violation';
            END IF;
            IF EXISTS (SELECT 1 FROM public.standards_sets s
                         JOIN jsonb_array_elements(v_payload->'rows') r ON r->>'code' = s.code
                        WHERE r->>'family' <> s.family) THEN
                RAISE EXCEPTION 'family_changed' USING ERRCODE = 'check_violation';
            END IF;
            INSERT INTO public.standards_sets (code, label, standard_refs, family)
            SELECT r->>'code', r->>'label',
                   coalesce(ARRAY(SELECT jsonb_array_elements_text(r->'standard_refs')), '{}'),
                   r->>'family'
              FROM jsonb_array_elements(v_payload->'rows') r
            ON CONFLICT (code) DO UPDATE
               SET label = EXCLUDED.label, standard_refs = EXCLUDED.standard_refs;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            RETURN v_rows;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION reference_set_publish(p_version_id uuid, p_approver text, p_reason text)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_drafted_by text;
            v_kind text;
        BEGIN
            SELECT v.drafted_by, s.kind INTO v_drafted_by, v_kind
              FROM public.reference_set_versions v
              JOIN public.reference_sets s ON s.key = v.set_key
             WHERE v.id = p_version_id AND v.status = 'draft'
               FOR UPDATE OF v;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'not_draft' USING ERRCODE = 'no_data_found';
            END IF;
            IF v_drafted_by = p_approver THEN
                RAISE EXCEPTION 'approver_is_drafter' USING ERRCODE = 'insufficient_privilege';
            END IF;
            UPDATE public.reference_set_versions
               SET status = 'published', approved_by = p_approver,
                   published_at = clock_timestamp()
             WHERE id = p_version_id;
            INSERT INTO public.reference_set_publications (version_id, action, operator,
                approver, reason)
            VALUES (p_version_id, 'published', v_drafted_by, p_approver, p_reason);
            IF v_kind = 'standards_sets' THEN
                PERFORM public.standards_sets_apply(p_version_id);
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION reference_set_withdraw(
            p_version_id uuid, p_operator text, p_approver text, p_reason text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_kind text;
        BEGIN
            IF p_operator = p_approver THEN
                RAISE EXCEPTION 'approver_is_operator' USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT s.kind INTO v_kind
              FROM public.reference_set_versions v
              JOIN public.reference_sets s ON s.key = v.set_key
             WHERE v.id = p_version_id AND v.status = 'published'
               FOR UPDATE OF v;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'not_published' USING ERRCODE = 'no_data_found';
            END IF;
            -- Withdrawing a standards set would orphan engagements' references: publish a
            -- correction instead.
            IF v_kind = 'standards_sets' THEN
                RAISE EXCEPTION 'standards_sets_not_withdrawable'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            UPDATE public.reference_set_versions
               SET status = 'withdrawn', withdrawn_by = p_operator,
                   withdrawal_approved_by = p_approver, withdrawn_at = clock_timestamp()
             WHERE id = p_version_id;
            INSERT INTO public.reference_set_publications (version_id, action, operator,
                approver, reason)
            VALUES (p_version_id, 'withdrawn', p_operator, p_approver, p_reason);
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION active_tenant_ids() RETURNS SETOF uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT f.tenant_id FROM public.firms f ORDER BY f.tenant_id
        $$
        """
    )

    for signature in _READERS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")
    for signature in (*_OWNER_ONLY, *_TRIGGER_FUNCTIONS):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM abacus_app")


def downgrade() -> None:
    for signature in (*_READERS, *_OWNER_ONLY):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE reference_set_publications")
    op.execute("DROP TABLE reference_set_versions")
    op.execute("DROP TABLE reference_sets")
    for signature in _TRIGGER_FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
