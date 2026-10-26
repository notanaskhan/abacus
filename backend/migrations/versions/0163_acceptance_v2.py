"""P-07-T35 (M5): acceptance and continuance in-app, CLI-07 (P-07 §4.2 M5; SPEC-332 AC-1 to AC-10;
DEC-372).

- `acceptance_questionnaire_templates` and `acceptance_questionnaire_template_versions` (both
  insert-only): the firm's questionnaires as database content, never code (rule 16). A version
  is immutable; its `sections` are `[{code, title}]`.
- `acceptance_records`: one per engagement, pinned to a template version. The app updates only
  the status, risk rating, the send-to-partner facts and the version. `acceptance_records_guard`
  refuses any change once the record is decided or declined (the lock), refuses a status move
  other than draft → awaiting partner → decided/declined, refuses decided/declined without the
  matching decision row, and refuses a delete.
- `acceptance_answers` (one row per answered section; the answers sealed) and
  `acceptance_manual_checks` (requested of a person, completed once, by that person, the note
  sealed; at most one open check per section). Neither changes once the record is locked.
- Insert-only, a person's only (`actor_kind`/`authored_kind = 'human'`): `acceptance_flags`
  (title and body sealed, source references), `acceptance_decisions` (one per record; the
  rationale sealed; `mfa_verified_at` required), `acceptance_conditions` (text sealed),
  `acceptance_condition_events` (one completion per condition, the note sealed),
  `risk_partner_reviews` (requested by the EP, completed only by the named partner).
- The human-only register gains `acceptance.decided` and `acceptance.review_completed` (0159's 33
  entries plus these two); the downgrade restores 0159's list.
- SPEC-025's `engagement_acceptance` rows are not converted here: G1 reads the v2 decision where a
  record exists and the legacy row otherwise, until P-07-T59 converts and drops it (DEC-372).

Revision ID: 0163
Revises: 0160
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0163"
down_revision = "0160"
branch_labels = None
depends_on = None

# The register as 0159 left it (33 entries).
_HUMAN_ONLY_0159 = sorted(
    [
        "assurance.phase_recorded",
        "contact.unlocked",
        "engagement.acceptance_recorded",
        "engagement.accepted",
        "engagement.letter_recorded",
        "eqr.eligibility_approved",
        "evidence.accepted",
        "firm.ai_client_data_opted_in",
        "firm_export.approved",
        "firm_export.declined",
        "follow_up.sent",
        "fulfilment.voided",
        "going_concern.decided",
        "guidance_draft.approved",
        "independence.confirmed",
        "independence.declined",
        "legal_hold.lifted",
        "legal_hold.placed",
        "materiality.decided",
        "portal_mfa.reset",
        "procedure.concluded",
        "report.approved",
        "report.released",
        "retention_policy.updated",
        "review.decided",
        "review.released",
        "review_decision.created",
        "review_decision.undone",
        "risk.approved",
        "sample.approved",
        "sign_off.recorded",
        "statement.approved",
        "team.approved",
    ]
)
_HUMAN_ONLY = sorted([*_HUMAN_ONLY_0159, "acceptance.decided", "acceptance.review_completed"])

_HUMAN = "text NOT NULL DEFAULT current_setting('app.actor_kind', true) CHECK ({col} = 'human')"
_SECTION = r"text NOT NULL CHECK (section_code ~ '^[a-z0-9_]{1,64}$')"
_SEALED = "bytea NOT NULL CHECK (octet_length({col}) <= 65536)"
_SEALED_NULL = "bytea NULL CHECK (octet_length({col}) <= 65536)"
_RECORD_FK = "FOREIGN KEY (tenant_id, record_id) REFERENCES acceptance_records (tenant_id, id)"

_INSERT_ONLY = (
    "acceptance_questionnaire_templates",
    "acceptance_questionnaire_template_versions",
    "acceptance_flags",
    "acceptance_decisions",
    "acceptance_conditions",
    "acceptance_condition_events",
    "risk_partner_reviews",
)
_LOCKED_CHILDREN = (
    "acceptance_answers",
    "acceptance_manual_checks",
    "acceptance_flags",
    "risk_partner_reviews",
)

_RECORD_GUARD = """
    CREATE FUNCTION acceptance_records_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'acceptance records are never deleted'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF OLD.status IN ('decided', 'declined') THEN
            RAISE EXCEPTION 'acceptance record % is locked', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status THEN
            IF NOT ((OLD.status = 'draft' AND NEW.status = 'awaiting_partner')
                    OR (OLD.status = 'awaiting_partner'
                        AND NEW.status IN ('decided', 'declined'))) THEN
                RAISE EXCEPTION 'acceptance record cannot move from % to %', OLD.status,
                    NEW.status USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.status IN ('decided', 'declined') AND NOT EXISTS (
                SELECT 1 FROM public.acceptance_decisions d
                 WHERE d.tenant_id = NEW.tenant_id AND d.record_id = NEW.id
                   AND (d.option = 'decline') = (NEW.status = 'declined')
            ) THEN
                RAISE EXCEPTION 'acceptance record % has no matching decision', NEW.id
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        NEW.updated_at := clock_timestamp();
        RETURN NEW;
    END $$
"""
_CHILD_LOCK = """
    CREATE FUNCTION acceptance_child_locked() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM public.acceptance_records r
             WHERE r.tenant_id = NEW.tenant_id AND r.id = NEW.record_id
               AND r.status IN ('decided', 'declined')
        ) THEN
            RAISE EXCEPTION 'acceptance record % is locked', NEW.record_id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
"""
_CHECK_COMPLETION = """
    CREATE FUNCTION acceptance_manual_checks_complete() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'manual checks are never deleted'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF OLD.completed_at IS NOT NULL THEN
            RAISE EXCEPTION 'manual check % is complete', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.completed_by IS DISTINCT FROM OLD.requested_of THEN
            RAISE EXCEPTION 'only the person asked completes a manual check'
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.completed_at := clock_timestamp();
        RETURN NEW;
    END $$
"""


def _immutable(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def upgrade() -> None:
    # --- the questionnaire templates (firm content) ----------------------------------------
    op.execute(
        """
        CREATE TABLE acceptance_questionnaire_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
            family text NOT NULL CHECK (family IN ('tax', 'audit_assurance', 'cas_advisory')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, name)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE acceptance_questionnaire_template_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no > 0),
            sections jsonb NOT NULL CHECK (
                jsonb_typeof(sections) = 'array'
                AND jsonb_array_length(sections) BETWEEN 1 AND 100
            ),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, template_id, version_no),
            FOREIGN KEY (tenant_id, template_id)
                REFERENCES acceptance_questionnaire_templates (tenant_id, id)
        )
        """
    )

    # --- the record --------------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE acceptance_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            client_id uuid NOT NULL,
            kind text NOT NULL
                CHECK (kind IN ('new_client', 'new_engagement_existing_client', 'continuance')),
            template_version_id uuid NOT NULL,
            prepared_by uuid NOT NULL,
            status text NOT NULL DEFAULT 'draft' CHECK (
                status IN ('draft', 'pre_screening', 'awaiting_partner', 'decided', 'declined')
            ),
            risk_rating text NULL CHECK (risk_rating IN ('low', 'moderate', 'high')),
            sent_to_partner_at timestamptz NULL,
            sent_to_partner_by uuid NULL,
            prescreen_run_id uuid NULL,
            prior_record_id uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id),
            CHECK ((sent_to_partner_at IS NULL) = (sent_to_partner_by IS NULL)),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES acceptance_questionnaire_template_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, prior_record_id) REFERENCES acceptance_records (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE acceptance_answers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            record_id uuid NOT NULL,
            section_code {_SECTION},
            answers_sealed {_SEALED_NULL.format(col="answers_sealed")},
            state text NOT NULL DEFAULT 'pending' CHECK (
                state IN ('pending', 'complete', 'flag', 'manual_check_open', 'manual_check_done')
            ),
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, record_id, section_code),
            {_RECORD_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE acceptance_manual_checks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            record_id uuid NOT NULL,
            section_code {_SECTION},
            requested_of uuid NOT NULL,
            requested_by uuid NOT NULL,
            requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            completed_by uuid NULL,
            completed_at timestamptz NULL,
            note_sealed {_SEALED_NULL.format(col="note_sealed")},
            CHECK ((completed_by IS NULL) = (completed_at IS NULL)),
            {_RECORD_FK}
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX acceptance_manual_checks_one_open ON acceptance_manual_checks "
        "(tenant_id, record_id, section_code) WHERE completed_at IS NULL"
    )

    # --- insert-only rows, a person's only ---------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE acceptance_flags (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            record_id uuid NOT NULL,
            severity text NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
            title_sealed {_SEALED.format(col="title_sealed")},
            body_sealed {_SEALED.format(col="body_sealed")},
            source_refs jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (
                jsonb_typeof(source_refs) = 'array' AND jsonb_array_length(source_refs) <= 20
            ),
            authored_by uuid NOT NULL,
            authored_kind {_HUMAN.format(col="authored_kind")},
            authored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            condition_id uuid NULL,
            {_RECORD_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE acceptance_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            record_id uuid NOT NULL,
            option text NOT NULL
                CHECK (option IN ('accept', 'accept_with_conditions', 'decline')),
            rationale_sealed {_SEALED.format(col="rationale_sealed")},
            decided_by uuid NOT NULL,
            decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            mfa_verified_at timestamptz NOT NULL,
            actor_kind {_HUMAN.format(col="actor_kind")},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, record_id),
            {_RECORD_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE acceptance_conditions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            record_id uuid NOT NULL,
            decision_id uuid NOT NULL,
            position smallint NOT NULL CHECK (position BETWEEN 1 AND 20),
            text_sealed {_SEALED.format(col="text_sealed")},
            assignee_user_id uuid NOT NULL,
            due_on date NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, decision_id, position),
            {_RECORD_FK},
            FOREIGN KEY (tenant_id, decision_id) REFERENCES acceptance_decisions (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE acceptance_condition_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            condition_id uuid NOT NULL,
            kind text NOT NULL DEFAULT 'completed' CHECK (kind = 'completed'),
            note_sealed {_SEALED_NULL.format(col="note_sealed")},
            actor_id uuid NOT NULL,
            actor_kind {_HUMAN.format(col="actor_kind")},
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, condition_id, kind),
            FOREIGN KEY (tenant_id, condition_id) REFERENCES acceptance_conditions (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE risk_partner_reviews (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            record_id uuid NOT NULL,
            event text NOT NULL CHECK (event IN ('requested', 'completed')),
            partner_id uuid NOT NULL,
            actor_id uuid NOT NULL,
            actor_kind {_HUMAN.format(col="actor_kind")},
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (event = 'requested' OR actor_id = partner_id),
            CHECK (event = 'completed' OR actor_id <> partner_id),
            {_RECORD_FK}
        )
        """
    )
    op.execute(
        "CREATE INDEX risk_partner_reviews_by_record ON risk_partner_reviews "
        "(tenant_id, record_id, at)"
    )
    for table in ("acceptance_flags", "acceptance_manual_checks", "acceptance_conditions"):
        op.execute(f"CREATE INDEX {table}_by_record ON {table} (tenant_id, record_id)")

    # --- row-level security, grants, guards --------------------------------------------------
    for table in (
        "acceptance_questionnaire_templates",
        "acceptance_questionnaire_template_versions",
        "acceptance_records",
        "acceptance_answers",
        "acceptance_manual_checks",
        "acceptance_flags",
        "acceptance_decisions",
        "acceptance_conditions",
        "acceptance_condition_events",
        "risk_partner_reviews",
    ):
        tenant_table(op, table)
    for table in _INSERT_ONLY:
        _immutable(table)
    insert_columns(
        op, "acceptance_questionnaire_templates", ("tenant_id", "name", "family", "created_by")
    )
    insert_columns(
        op,
        "acceptance_questionnaire_template_versions",
        ("tenant_id", "template_id", "version_no", "sections", "created_by"),
    )
    insert_columns(
        op,
        "acceptance_records",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "client_id",
            "kind",
            "template_version_id",
            "prepared_by",
            "prior_record_id",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON acceptance_records FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, risk_rating, sent_to_partner_at, sent_to_partner_by, version) "
        "ON acceptance_records TO abacus_app"
    )
    op.execute(_RECORD_GUARD)
    op.execute(
        "CREATE TRIGGER acceptance_records_guard BEFORE UPDATE OR DELETE ON acceptance_records "
        "FOR EACH ROW EXECUTE FUNCTION acceptance_records_guard()"
    )
    insert_columns(
        op,
        "acceptance_answers",
        ("tenant_id", "record_id", "section_code", "answers_sealed", "state", "updated_by"),
    )
    op.execute("REVOKE UPDATE, DELETE ON acceptance_answers FROM abacus_app")
    op.execute(
        "GRANT UPDATE (answers_sealed, state, version, updated_by, updated_at) "
        "ON acceptance_answers TO abacus_app"
    )
    insert_columns(
        op,
        "acceptance_manual_checks",
        ("id", "tenant_id", "record_id", "section_code", "requested_of", "requested_by"),
    )
    op.execute("REVOKE UPDATE, DELETE ON acceptance_manual_checks FROM abacus_app")
    op.execute(
        "GRANT UPDATE (completed_by, note_sealed) ON acceptance_manual_checks TO abacus_app"
    )
    op.execute(_CHECK_COMPLETION)
    op.execute(
        "CREATE TRIGGER acceptance_manual_checks_complete BEFORE UPDATE OR DELETE "
        "ON acceptance_manual_checks FOR EACH ROW "
        "EXECUTE FUNCTION acceptance_manual_checks_complete()"
    )
    op.execute(_CHILD_LOCK)
    for table in _LOCKED_CHILDREN:
        op.execute(
            f"CREATE TRIGGER {table}_locked BEFORE INSERT OR UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION acceptance_child_locked()"
        )
    insert_columns(
        op,
        "acceptance_flags",
        (
            "id",
            "tenant_id",
            "record_id",
            "severity",
            "title_sealed",
            "body_sealed",
            "source_refs",
            "authored_by",
        ),
    )
    insert_columns(
        op,
        "acceptance_decisions",
        (
            "id",
            "tenant_id",
            "record_id",
            "option",
            "rationale_sealed",
            "decided_by",
            "mfa_verified_at",
        ),
    )
    insert_columns(
        op,
        "acceptance_conditions",
        (
            "id",
            "tenant_id",
            "record_id",
            "decision_id",
            "position",
            "text_sealed",
            "assignee_user_id",
            "due_on",
        ),
    )
    insert_columns(
        op,
        "acceptance_condition_events",
        ("id", "tenant_id", "condition_id", "note_sealed", "actor_id"),
    )
    insert_columns(
        op, "risk_partner_reviews", ("tenant_id", "record_id", "event", "partner_id", "actor_id")
    )

    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_HUMAN_ONLY_0159)
    for table in (
        "risk_partner_reviews",
        "acceptance_condition_events",
        "acceptance_conditions",
        "acceptance_decisions",
        "acceptance_flags",
        "acceptance_manual_checks",
        "acceptance_answers",
        "acceptance_records",
        "acceptance_questionnaire_template_versions",
        "acceptance_questionnaire_templates",
    ):
        op.execute(f"DROP TABLE {table}")
    for table in _INSERT_ONLY:
        op.execute(f"DROP FUNCTION {table}_immutable()")
    op.execute("DROP FUNCTION acceptance_child_locked()")
    op.execute("DROP FUNCTION acceptance_manual_checks_complete()")
    op.execute("DROP FUNCTION acceptance_records_guard()")
