"""T-03 season readiness (T-03-T03; T-03 §4.2; DEC-2202; expand-only).

`requests` (the organizer editor, on top of T-02's 0467):
- `questionnaire_templates` gains `key`, `form_family` and `owner_id` (a partner member).
- `questionnaire_template_versions` gains the editor's lifecycle: `status` (draft, published,
  discarded; null on T-02's imported versions, whose state stays `published_at`), the
  questionnaire that holds the version's structure, `applies_to_tax_year`, `drafted_from`, a
  change summary, `published_actor_kind` (human only) and `row_version`. One draft per template
  (partial unique index); a published editor version names its tax year. Imported versions keep
  `content` and their file hash; editor versions hold neither.
- `questionnaires` gains `owner_kind` (binder or template_version) and
  `source_template_version_id`; a template-owned questionnaire has no engagement or work item.
- `questionnaire_sections` gains `key` and `retired_at`; `questions` gains the editor columns
  (`internal_helper`, `required`, `show_when`, `choices`, `amount_parts`, `effect_rules`,
  `retired_at`, `origin_template_question_key`) and the type `date`.
- `answer_versions` gains `question_wording_hash` (the wording the client answered).
- `answer_effects` (new, insert-only): one row per answer and rule.
- A trigger refuses any change to a published version, and to the sections and questions of a
  questionnaire a published version owns.

`tax` (extensions and estimates):
- `filing_extensions` per return and jurisdiction; `extension_payments` (an approved payment is
  frozen, `approved_actor_kind` human only; a change supersedes it); `estimate_schedules` per
  client, tax year and jurisdiction; `estimate_installments` per quarter.

Every amount, answer value and reject code is TRI; names confidential; templates internal. No
rule or template content is inserted (AGENTS 16).

Revision ID: 0655
Revises: 0654
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0655"
down_revision = "0654"
branch_labels = None
depends_on = None

_NEW_TABLES = (
    "answer_effects",
    "filing_extensions",
    "extension_payments",
    "estimate_schedules",
    "estimate_installments",
)
_SHA = "~ '^[0-9a-f]{64}$'"
_KEY = "~ '^[a-z][a-z0-9_]{0,39}(\\.[a-z][a-z0-9_]{0,39})?$'"
_MONEY = "numeric(18,2)"

_FROZEN = """
    CREATE FUNCTION t03_frozen_row() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        RAISE EXCEPTION '% rows are insert-only', TG_TABLE_NAME
            USING ERRCODE = 'insufficient_privilege';
    END $$
"""

# A published editor version never changes; T-02's imported versions keep their one update
# (setting published_at/by), so the guard reads `status`.
_VERSION_FROZEN = """
    CREATE FUNCTION questionnaire_template_versions_frozen() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF OLD.status = 'published' THEN
            RAISE EXCEPTION 'a published organizer version never changes'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END $$
"""

# The sections and questions of a questionnaire that a published version owns are frozen too.
_STRUCTURE_FROZEN = """
    CREATE FUNCTION questionnaire_structure_frozen() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        v_published boolean;
    BEGIN
        SELECT EXISTS (
            SELECT 1 FROM public.questionnaire_template_versions v
             WHERE v.tenant_id = OLD.tenant_id
               AND v.questionnaire_id = OLD.questionnaire_id
               AND v.status = 'published'
        ) INTO v_published;
        IF v_published THEN
            RAISE EXCEPTION 'a published organizer version''s questions never change'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END $$
"""

# An approved payment is frozen; the only update before approval is the approval itself and the
# paid date and confirmation evidence (recorded when staff accept the client's upload).
_PAYMENT_FROZEN = """
    CREATE FUNCTION extension_payments_frozen() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'extension payments are never deleted'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF OLD.approved_at IS NOT NULL AND (
            NEW.amount IS DISTINCT FROM OLD.amount
            OR NEW.kind IS DISTINCT FROM OLD.kind
            OR NEW.approved_by IS DISTINCT FROM OLD.approved_by
            OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
            OR NEW.approved_actor_kind IS DISTINCT FROM OLD.approved_actor_kind
            OR NEW.filing_extension_id IS DISTINCT FROM OLD.filing_extension_id
            OR (OLD.paid_on IS NOT NULL AND NEW.paid_on IS DISTINCT FROM OLD.paid_on)
            OR (OLD.confirmation_evidence_version_id IS NOT NULL
                AND NEW.confirmation_evidence_version_id
                    IS DISTINCT FROM OLD.confirmation_evidence_version_id)
        ) THEN
            RAISE EXCEPTION 'an approved extension payment never changes; supersede it'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
"""


def _requests_upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE questionnaire_templates
            ADD COLUMN key text NULL CHECK (key {_KEY}),
            ADD COLUMN form_family text NULL
                CHECK (form_family IN ('1040', '1041', '1065', '1120s', '1120', '990', '706')),
            ADD COLUMN owner_id uuid NULL
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX questionnaire_templates_one_key ON questionnaire_templates "
        "(tenant_id, key) WHERE key IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE questionnaire_template_versions "
        "ALTER COLUMN content DROP NOT NULL, ALTER COLUMN source_file_sha256 DROP NOT NULL"
    )
    op.execute(
        """
        ALTER TABLE questionnaire_template_versions
            ADD COLUMN status text NULL CHECK (status IN ('draft', 'published', 'discarded')),
            ADD COLUMN questionnaire_id uuid NULL,
            ADD COLUMN applies_to_tax_year integer NULL
                CHECK (applies_to_tax_year BETWEEN 2000 AND 2100),
            ADD COLUMN drafted_from_version_id uuid NULL,
            ADD COLUMN change_summary text NULL CHECK (length(change_summary) <= 500),
            ADD COLUMN drafted_by uuid NULL,
            ADD COLUMN published_actor_kind text NULL CHECK (published_actor_kind = 'human'),
            ADD COLUMN row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            ADD CONSTRAINT questionnaire_template_versions_source CHECK (
                (status IS NULL AND content IS NOT NULL AND source_file_sha256 IS NOT NULL)
                OR (status IS NOT NULL AND questionnaire_id IS NOT NULL AND drafted_by IS NOT NULL)
            ),
            ADD CONSTRAINT questionnaire_template_versions_tax_year
                CHECK (status IS DISTINCT FROM 'published' OR applies_to_tax_year IS NOT NULL),
            ADD CONSTRAINT questionnaire_template_versions_human
                CHECK (status IS DISTINCT FROM 'published' OR published_actor_kind = 'human'),
            ADD FOREIGN KEY (tenant_id, questionnaire_id)
                REFERENCES questionnaires (tenant_id, id),
            ADD FOREIGN KEY (tenant_id, drafted_from_version_id)
                REFERENCES questionnaire_template_versions (tenant_id, id)
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX questionnaire_template_versions_one_draft "
        "ON questionnaire_template_versions (tenant_id, template_id) WHERE status = 'draft'"
    )
    op.execute(
        "ALTER TABLE questionnaires "
        "ALTER COLUMN engagement_id DROP NOT NULL, ALTER COLUMN work_item_id DROP NOT NULL"
    )
    op.execute(
        """
        ALTER TABLE questionnaires
            ADD COLUMN owner_kind text NOT NULL DEFAULT 'binder'
                CHECK (owner_kind IN ('binder', 'template_version')),
            ADD COLUMN source_template_version_id uuid NULL,
            DROP CONSTRAINT questionnaires_organizer_template,
            ADD CONSTRAINT questionnaires_organizer_template CHECK (
                kind <> 'organizer' OR owner_kind = 'template_version'
                OR template_version_id IS NOT NULL
            ),
            ADD CONSTRAINT questionnaires_owner CHECK (
                owner_kind = 'template_version'
                OR (engagement_id IS NOT NULL AND work_item_id IS NOT NULL)
            ),
            ADD FOREIGN KEY (tenant_id, source_template_version_id)
                REFERENCES questionnaire_template_versions (tenant_id, id)
        """
    )
    op.execute(
        f"""
        ALTER TABLE questionnaire_sections
            ADD COLUMN key text NULL CHECK (key {_KEY}),
            ADD COLUMN retired_at timestamptz NULL
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX questionnaire_sections_one_key ON questionnaire_sections "
        "(tenant_id, questionnaire_id, key) WHERE key IS NOT NULL"
    )
    op.execute("ALTER TABLE questions DROP CONSTRAINT questions_type_check")
    op.execute(
        "ALTER TABLE questions ADD CONSTRAINT questions_type_check CHECK (type IN ('yes_no', "
        "'amount_group', 'upload_if_yes', 'long_text', 'choice', 'date'))"
    )
    op.execute(
        """
        ALTER TABLE questions
            ADD COLUMN internal_helper text NULL CHECK (length(internal_helper) <= 500),
            ADD COLUMN required boolean NOT NULL DEFAULT false,
            ADD COLUMN show_when jsonb NULL CHECK (show_when IS NULL OR (
                jsonb_typeof(show_when) = 'object'
                AND show_when ? 'parent_key' AND show_when ? 'equals')),
            ADD COLUMN choices jsonb NULL
                CHECK (choices IS NULL OR jsonb_typeof(choices) = 'array'),
            ADD COLUMN amount_parts jsonb NULL
                CHECK (amount_parts IS NULL OR jsonb_typeof(amount_parts) = 'array'),
            ADD COLUMN effect_rules jsonb NULL
                CHECK (effect_rules IS NULL OR jsonb_typeof(effect_rules) = 'array'),
            ADD COLUMN retired_at timestamptz NULL,
            ADD COLUMN origin_template_question_key text NULL
                CHECK (origin_template_question_key ~ '^[a-z0-9][a-z0-9_.-]{0,79}$'),
            ADD CONSTRAINT questions_show_when_parent
                CHECK (show_when IS NULL OR conditional_on_question_id IS NOT NULL)
        """
    )
    op.execute(
        f"ALTER TABLE answer_versions ADD COLUMN question_wording_hash text NULL "
        f"CHECK (question_wording_hash {_SHA})"
    )
    op.execute(
        f"""
        CREATE TABLE answer_effects (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            answer_id uuid NULL,
            question_id uuid NOT NULL,
            rule_key text NOT NULL CHECK (rule_key {_KEY}),
            effect_kind text NOT NULL CHECK (effect_kind IN ('request_item_created',
                'review_point_raised', 'internal_review_flagged', 'upload_routed_to_notices',
                'pending_handler')),
            target_type text NULL CHECK (target_type ~ '^[a-z][a-z0-9_]{{0,39}}$'),
            target_id uuid NULL,
            actor_kind text NOT NULL CHECK (actor_kind IN ('system', 'human')),
            actor_user_id uuid NULL,
            template_version_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT answer_effects_target CHECK ((target_type IS NULL) = (target_id IS NULL)),
            CONSTRAINT answer_effects_editor
                CHECK (answer_id IS NOT NULL
                    OR (actor_kind = 'human' AND actor_user_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, answer_id) REFERENCES answer_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, question_id) REFERENCES questions (tenant_id, id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES questionnaire_template_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX answer_effects_once ON answer_effects "
        "(tenant_id, answer_id, rule_key) WHERE answer_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX answer_effects_once_per_edit ON answer_effects "
        "(tenant_id, question_id, rule_key) WHERE answer_id IS NULL"
    )
    op.execute("CREATE INDEX answer_effects_question ON answer_effects (tenant_id, question_id)")


def _tax_upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE filing_extensions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            tax_return_id uuid NOT NULL,
            tax_year integer NOT NULL CHECK (tax_year BETWEEN 2000 AND 2100),
            jurisdiction text NOT NULL CHECK (jurisdiction ~ '^[A-Z]{{2,12}}$'),
            form text NOT NULL CHECK (form ~ '^[A-Z0-9-]{{2,12}}$'),
            status text NOT NULL DEFAULT 'not_filed'
                CHECK (status IN ('not_filed', 'prepared', 'filed', 'accepted', 'rejected')),
            likely_to_extend boolean NOT NULL DEFAULT false,
            likely_reasons text[] NOT NULL DEFAULT '{{}}' CHECK (likely_reasons <@ ARRAY[
                'k1_outstanding', 'binder_incomplete', 'engagement_not_accepted',
                'preparer_flag']::text[]),
            likely_note text NULL CHECK (length(likely_note) <= 500),
            original_due_on date NOT NULL,
            extended_due_on date NOT NULL,
            due_rules_version_id uuid NULL,
            filed_on date NULL,
            filed_recorded_by uuid NULL,
            filed_form_evidence_version_id uuid NULL,
            ack_received_at timestamptz NULL,
            reject_code text NULL CHECK (reject_code ~ '^[A-Z0-9-]{{2,20}}$'),
            projected_liability {_MONEY} NULL CHECK (projected_liability >= 0),
            projected_liability_source text NULL
                CHECK (projected_liability_source IN ('engine_import', 'preparer_entry')),
            projected_liability_ref jsonb NULL,
            withholding_plus_estimates {_MONEY} NULL CHECK (withholding_plus_estimates >= 0),
            safe_harbor_pct numeric(5,2) NULL CHECK (safe_harbor_pct BETWEEN 0 AND 110),
            safe_harbor_target {_MONEY} NULL CHECK (safe_harbor_target >= 0),
            engine_version text NULL,
            inputs_hash text NULL CHECK (inputs_hash {_SHA}),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            UNIQUE (tenant_id, id),
            CONSTRAINT filing_extensions_one UNIQUE (tenant_id, tax_return_id, jurisdiction),
            CONSTRAINT filing_extensions_due CHECK (extended_due_on >= original_due_on),
            CONSTRAINT filing_extensions_filed CHECK (
                status IN ('not_filed', 'prepared')
                OR (filed_on IS NOT NULL AND filed_recorded_by IS NOT NULL)
            ),
            CONSTRAINT filing_extensions_rejected
                CHECK (status <> 'rejected' OR reject_code IS NOT NULL),
            CONSTRAINT filing_extensions_stamped CHECK (
                safe_harbor_target IS NULL
                OR (engine_version IS NOT NULL AND inputs_hash IS NOT NULL)
            ),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tax_return_id) REFERENCES tax_returns (work_item_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX filing_extensions_year ON filing_extensions (tenant_id, tax_year, status)"
    )
    op.execute(
        f"""
        CREATE TABLE extension_payments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            filing_extension_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('extension_payment', 'ptet')),
            amount {_MONEY} NOT NULL CHECK (amount > 0),
            paid_on date NULL,
            proposed_by uuid NOT NULL,
            proposed_at timestamptz NOT NULL DEFAULT abacus_now(),
            approved_by uuid NULL,
            approved_actor_kind text NULL CHECK (approved_actor_kind = 'human'),
            approved_at timestamptz NULL,
            supersedes_id uuid NULL,
            confirmation_evidence_version_id uuid NULL,
            UNIQUE (tenant_id, id),
            CONSTRAINT extension_payments_approved CHECK (
                (approved_by IS NULL AND approved_at IS NULL AND approved_actor_kind IS NULL)
                OR (approved_by IS NOT NULL AND approved_at IS NOT NULL
                    AND approved_actor_kind = 'human')
            ),
            FOREIGN KEY (tenant_id, filing_extension_id)
                REFERENCES filing_extensions (tenant_id, id),
            FOREIGN KEY (tenant_id, supersedes_id) REFERENCES extension_payments (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX extension_payments_superseded_once ON extension_payments "
        "(tenant_id, supersedes_id) WHERE supersedes_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX extension_payments_extension ON extension_payments "
        "(tenant_id, filing_extension_id)"
    )
    op.execute(
        f"""
        CREATE TABLE estimate_schedules (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            basis_tax_return_id uuid NULL,
            tax_year integer NOT NULL CHECK (tax_year BETWEEN 2000 AND 2100),
            jurisdiction text NOT NULL CHECK (jurisdiction ~ '^[A-Z]{{2,12}}$'),
            form text NOT NULL CHECK (form ~ '^[A-Z0-9-]{{2,16}}$'),
            method text NOT NULL CHECK (method IN ('prior_year_100', 'prior_year_110',
                'current_year_90', 'not_required_withholding', 'not_required_estate_first_years',
                'prospect')),
            prior_year_tax {_MONEY} NULL CHECK (prior_year_tax >= 0),
            prior_year_tax_ref jsonb NULL,
            prior_agi_over_threshold boolean NULL,
            projected_withholding {_MONEY} NULL CHECK (projected_withholding >= 0),
            annual_required {_MONEY} NULL CHECK (annual_required >= 0),
            engine_version text NULL,
            inputs_hash text NULL CHECK (inputs_hash {_SHA}),
            payment_method_label text NULL CHECK (payment_method_label IN ('irs_direct_pay',
                'eftps', 'ny_online_services', 'state_portal', 'check', 'other')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            UNIQUE (tenant_id, id),
            CONSTRAINT estimate_schedules_one
                UNIQUE (tenant_id, client_entity_id, tax_year, jurisdiction),
            CONSTRAINT estimate_schedules_stamped CHECK (
                annual_required IS NULL OR (engine_version IS NOT NULL AND inputs_hash IS NOT NULL)
            ),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (basis_tax_return_id) REFERENCES tax_returns (work_item_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE estimate_installments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            schedule_id uuid NOT NULL,
            quarter smallint NOT NULL CHECK (quarter BETWEEN 1 AND 4),
            due_on date NOT NULL,
            due_rules_version_id uuid NULL,
            amount {_MONEY} NULL CHECK (amount >= 0),
            status text NOT NULL DEFAULT 'not_confirmed' CHECK (status IN ('not_confirmed',
                'confirmation_requested', 'scheduled', 'paid', 'not_required')),
            scheduled_for date NULL,
            paid_on date NULL,
            confirmation_request_item_id uuid NULL,
            confirmed_by_contact_id uuid NULL,
            confirmed_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            UNIQUE (tenant_id, id),
            CONSTRAINT estimate_installments_one UNIQUE (tenant_id, schedule_id, quarter),
            CONSTRAINT estimate_installments_scheduled
                CHECK (status <> 'scheduled' OR scheduled_for IS NOT NULL),
            CONSTRAINT estimate_installments_paid CHECK (status <> 'paid' OR paid_on IS NOT NULL),
            FOREIGN KEY (tenant_id, schedule_id) REFERENCES estimate_schedules (tenant_id, id)
        )
        """
    )


def _grants() -> None:
    for table in _NEW_TABLES:
        tenant_table(op, table)
    # requests: the editor's columns.
    op.execute(
        "GRANT UPDATE (key, form_family, owner_id) ON questionnaire_templates TO abacus_app"
    )
    op.execute(
        "GRANT INSERT (status, questionnaire_id, applies_to_tax_year, drafted_from_version_id, "
        "change_summary, drafted_by) ON questionnaire_template_versions TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (status, questionnaire_id, applies_to_tax_year, change_summary, "
        "published_actor_kind, row_version) ON questionnaire_template_versions TO abacus_app"
    )
    op.execute(
        "GRANT INSERT (owner_kind, source_template_version_id) ON questionnaires TO abacus_app"
    )
    op.execute("GRANT INSERT (key) ON questionnaire_sections TO abacus_app")
    op.execute(
        "GRANT UPDATE (name, position, key, retired_at) ON questionnaire_sections TO abacus_app"
    )
    op.execute(
        "GRANT INSERT (internal_helper, required, show_when, choices, amount_parts, "
        "effect_rules, origin_template_question_key) ON questions TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (section_id, position, client_wording, help_text, internal_helper, "
        "required, show_when, conditional_on_question_id, conditional_value, choices, "
        "amount_parts, effect_rules, retired_at, type) ON questions TO abacus_app"
    )
    op.execute("GRANT INSERT (question_wording_hash) ON answer_versions TO abacus_app")
    insert_only(op, "answer_effects")
    insert_columns(
        op,
        "answer_effects",
        (
            "tenant_id",
            "answer_id",
            "question_id",
            "rule_key",
            "effect_kind",
            "target_type",
            "target_id",
            "actor_kind",
            "actor_user_id",
            "template_version_id",
        ),
    )
    # tax.
    insert_columns(
        op,
        "filing_extensions",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "tax_return_id",
            "tax_year",
            "jurisdiction",
            "form",
            "status",
            "likely_to_extend",
            "likely_reasons",
            "likely_note",
            "original_due_on",
            "extended_due_on",
            "due_rules_version_id",
            "projected_liability",
            "projected_liability_source",
            "projected_liability_ref",
            "withholding_plus_estimates",
            "safe_harbor_pct",
            "safe_harbor_target",
            "engine_version",
            "inputs_hash",
            "created_by",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON filing_extensions FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, likely_to_extend, likely_reasons, likely_note, original_due_on, "
        "extended_due_on, due_rules_version_id, filed_on, filed_recorded_by, form, "
        "filed_form_evidence_version_id, ack_received_at, reject_code, projected_liability, "
        "projected_liability_source, projected_liability_ref, withholding_plus_estimates, "
        "safe_harbor_pct, safe_harbor_target, engine_version, inputs_hash, row_version) "
        "ON filing_extensions TO abacus_app"
    )
    insert_columns(
        op,
        "extension_payments",
        (
            "id",
            "tenant_id",
            "filing_extension_id",
            "kind",
            "amount",
            "paid_on",
            "proposed_by",
            "supersedes_id",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON extension_payments FROM abacus_app")
    op.execute(
        "GRANT UPDATE (approved_by, approved_actor_kind, approved_at, paid_on, "
        "confirmation_evidence_version_id) ON extension_payments TO abacus_app"
    )
    insert_columns(
        op,
        "estimate_schedules",
        (
            "id",
            "tenant_id",
            "client_entity_id",
            "basis_tax_return_id",
            "tax_year",
            "jurisdiction",
            "form",
            "method",
            "prior_year_tax",
            "prior_year_tax_ref",
            "prior_agi_over_threshold",
            "projected_withholding",
            "annual_required",
            "engine_version",
            "inputs_hash",
            "payment_method_label",
            "created_by",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON estimate_schedules FROM abacus_app")
    op.execute(
        "GRANT UPDATE (method, prior_year_tax, prior_year_tax_ref, prior_agi_over_threshold, "
        "projected_withholding, annual_required, engine_version, inputs_hash, "
        "payment_method_label, row_version) ON estimate_schedules TO abacus_app"
    )
    insert_columns(
        op,
        "estimate_installments",
        (
            "id",
            "tenant_id",
            "schedule_id",
            "quarter",
            "due_on",
            "due_rules_version_id",
            "amount",
            "status",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON estimate_installments FROM abacus_app")
    op.execute(
        "GRANT UPDATE (due_on, due_rules_version_id, amount, status, scheduled_for, paid_on, "
        "confirmation_request_item_id, confirmed_by_contact_id, confirmed_at, row_version) "
        "ON estimate_installments TO abacus_app"
    )


def _triggers() -> None:
    for table in _NEW_TABLES:
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    op.execute(_FROZEN)
    op.execute(
        "CREATE TRIGGER answer_effects_immutable BEFORE UPDATE OR DELETE ON answer_effects "
        "FOR EACH ROW EXECUTE FUNCTION t03_frozen_row()"
    )
    op.execute("REVOKE TRUNCATE ON answer_effects FROM abacus_app")
    op.execute(
        "CREATE TRIGGER answer_effects_no_truncate BEFORE TRUNCATE ON answer_effects "
        "FOR EACH STATEMENT EXECUTE FUNCTION t03_frozen_row()"
    )
    op.execute(_VERSION_FROZEN)
    op.execute(
        "CREATE TRIGGER questionnaire_template_versions_frozen BEFORE UPDATE OR DELETE "
        "ON questionnaire_template_versions FOR EACH ROW "
        "EXECUTE FUNCTION questionnaire_template_versions_frozen()"
    )
    op.execute(_STRUCTURE_FROZEN)
    for table in ("questionnaire_sections", "questions"):
        op.execute(
            f"CREATE TRIGGER {table}_frozen BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION questionnaire_structure_frozen()"
        )
    op.execute(_PAYMENT_FROZEN)
    op.execute(
        "CREATE TRIGGER extension_payments_frozen BEFORE UPDATE OR DELETE ON extension_payments "
        "FOR EACH ROW EXECUTE FUNCTION extension_payments_frozen()"
    )
    for function in (
        "t03_frozen_row",
        "questionnaire_template_versions_frozen",
        "questionnaire_structure_frozen",
        "extension_payments_frozen",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function}() FROM PUBLIC")


def upgrade() -> None:
    _requests_upgrade()
    _tax_upgrade()
    _grants()
    _triggers()


def downgrade() -> None:
    op.execute("DROP TRIGGER extension_payments_frozen ON extension_payments")
    op.execute("DROP FUNCTION extension_payments_frozen()")
    for table in ("questionnaire_sections", "questions"):
        op.execute(f"DROP TRIGGER {table}_frozen ON {table}")
    op.execute("DROP FUNCTION questionnaire_structure_frozen()")
    op.execute(
        "DROP TRIGGER questionnaire_template_versions_frozen ON questionnaire_template_versions"
    )
    op.execute("DROP FUNCTION questionnaire_template_versions_frozen()")
    for table in reversed(_NEW_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION t03_frozen_row()")
    op.execute("ALTER TABLE answer_versions DROP COLUMN question_wording_hash")
    op.execute(
        "ALTER TABLE questions DROP CONSTRAINT questions_show_when_parent, "
        "DROP COLUMN internal_helper, DROP COLUMN required, DROP COLUMN show_when, "
        "DROP COLUMN choices, DROP COLUMN amount_parts, DROP COLUMN effect_rules, "
        "DROP COLUMN retired_at, DROP COLUMN origin_template_question_key"
    )
    op.execute("ALTER TABLE questions DROP CONSTRAINT questions_type_check")
    op.execute(
        "ALTER TABLE questions ADD CONSTRAINT questions_type_check CHECK (type IN ('yes_no', "
        "'amount_group', 'upload_if_yes', 'long_text', 'choice'))"
    )
    op.execute("DROP INDEX questionnaire_sections_one_key")
    op.execute("ALTER TABLE questionnaire_sections DROP COLUMN key, DROP COLUMN retired_at")
    op.execute(
        "ALTER TABLE questionnaires DROP CONSTRAINT questionnaires_owner, "
        "DROP CONSTRAINT questionnaires_organizer_template, "
        "DROP COLUMN owner_kind, DROP COLUMN source_template_version_id, "
        "ADD CONSTRAINT questionnaires_organizer_template "
        "CHECK (kind <> 'organizer' OR template_version_id IS NOT NULL)"
    )
    op.execute(
        "ALTER TABLE questionnaires "
        "ALTER COLUMN engagement_id SET NOT NULL, ALTER COLUMN work_item_id SET NOT NULL"
    )
    op.execute("DROP INDEX questionnaire_template_versions_one_draft")
    op.execute(
        "ALTER TABLE questionnaire_template_versions "
        "DROP CONSTRAINT questionnaire_template_versions_source, "
        "DROP CONSTRAINT questionnaire_template_versions_tax_year, "
        "DROP CONSTRAINT questionnaire_template_versions_human, "
        "DROP COLUMN status, DROP COLUMN questionnaire_id, DROP COLUMN applies_to_tax_year, "
        "DROP COLUMN drafted_from_version_id, DROP COLUMN change_summary, DROP COLUMN drafted_by, "
        "DROP COLUMN published_actor_kind, DROP COLUMN row_version"
    )
    op.execute(
        "ALTER TABLE questionnaire_template_versions "
        "ALTER COLUMN content SET NOT NULL, ALTER COLUMN source_file_sha256 SET NOT NULL"
    )
    op.execute("DROP INDEX questionnaire_templates_one_key")
    op.execute(
        "ALTER TABLE questionnaire_templates DROP COLUMN key, DROP COLUMN form_family, "
        "DROP COLUMN owner_id"
    )
