"""Questionnaires v1 (T-02-T16; T-02 §4.2 `questionnaires`; DEC-1369; expand-only).

Six tables, owned by `requests`, tenant-scoped with forced RLS:

- `questionnaire_templates` and insert-only `questionnaire_template_versions`: organizer templates
  are the firm's database content, imported (CSV, XLSX or JSON) and published by a person. A
  version's `content` holds its sections and questions; `published_at`/`published_by` are set once
  (the only update); "current" and "superseded" are computed (the newest published is current).
- `questionnaires`: an organizer on a request list, or team questions and inquiries a team creates
  (an inquiry names its addressee). `data_class` is `tri` for organizers.
- `questionnaire_sections` and `questions`: instantiated by code from a version (prior-year values
  copied by code, never by a model), or drafted by the team (`origin` team); a person sends each.
- `answer_versions` (insert-only): the current answer is the highest `version_no`; a trigger
  refuses a new answer once the questionnaire is `submitted`.

No template text is inserted here (AGENTS 16): templates arrive through the import.

Revision ID: 0467
Revises: 0430 (main's head when built; re-chain after the S18 lane's 0466 at the batch merge)
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0467"
down_revision = "0430"
branch_labels = None
depends_on = None

_TABLES = (
    "questionnaire_templates",
    "questionnaire_template_versions",
    "questionnaires",
    "questionnaire_sections",
    "questions",
    "answer_versions",
)

_LOCKED = """
    CREATE FUNCTION answer_versions_locked() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        v_status text;
    BEGIN
        SELECT q.status INTO v_status FROM public.questionnaires q
          JOIN public.questions x ON x.questionnaire_id = q.id AND x.tenant_id = q.tenant_id
         WHERE x.tenant_id = NEW.tenant_id AND x.id = NEW.question_id
         FOR SHARE OF q;
        IF v_status = 'submitted' THEN
            RAISE EXCEPTION 'a submitted questionnaire''s answers are locked'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
"""


_IMMUTABLE = """
    CREATE FUNCTION answer_versions_immutable() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        RAISE EXCEPTION 'answer versions are insert-only' USING ERRCODE = 'insufficient_privilege';
    END $$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE questionnaire_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT questionnaire_templates_one_name UNIQUE (tenant_id, name)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE questionnaire_template_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            content jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object'),
            source_file_sha256 text NOT NULL CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
            imported_by uuid NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT abacus_now(),
            published_by uuid NULL,
            published_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            CONSTRAINT questionnaire_template_versions_one
                UNIQUE (tenant_id, template_id, version),
            CONSTRAINT questionnaire_template_versions_published
                CHECK ((published_by IS NULL) = (published_at IS NULL)),
            FOREIGN KEY (tenant_id, template_id) REFERENCES questionnaire_templates (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE questionnaires (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            request_list_id uuid NULL,
            kind text NOT NULL CHECK (kind IN ('organizer', 'team_questions', 'inquiry')),
            template_version_id uuid NULL,
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
            due_on date NULL,
            addressed_to_contact_id uuid NULL,
            status text NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'complete', 'submitted')),
            completed_by uuid NULL,
            completed_at timestamptz NULL,
            submitted_by uuid NULL,
            submitted_at timestamptz NULL,
            data_class text NULL CHECK (data_class IN ('tri')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            UNIQUE (tenant_id, id),
            CONSTRAINT questionnaires_inquiry_addressed
                CHECK (kind <> 'inquiry' OR addressed_to_contact_id IS NOT NULL),
            CONSTRAINT questionnaires_organizer_template
                CHECK (kind <> 'organizer' OR template_version_id IS NOT NULL),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES questionnaire_template_versions (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX questionnaires_work_item ON questionnaires (tenant_id, work_item_id)")
    op.execute(
        """
        CREATE TABLE questionnaire_sections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            questionnaire_id uuid NOT NULL,
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 80),
            icon_key text NULL CHECK (icon_key ~ '^[a-z][a-z0-9-]{0,39}$'),
            position integer NOT NULL CHECK (position >= 0),
            UNIQUE (tenant_id, id),
            CONSTRAINT questionnaire_sections_one UNIQUE (tenant_id, questionnaire_id, name),
            FOREIGN KEY (tenant_id, questionnaire_id) REFERENCES questionnaires (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE questions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            questionnaire_id uuid NOT NULL,
            section_id uuid NOT NULL,
            question_key text NULL CHECK (question_key ~ '^[a-z0-9][a-z0-9_.-]{0,79}$'),
            position integer NOT NULL CHECK (position >= 0),
            type text NOT NULL CHECK (type IN ('yes_no', 'amount_group', 'upload_if_yes',
                'long_text', 'choice')),
            client_wording text NOT NULL CHECK (length(btrim(client_wording)) BETWEEN 1 AND 2000),
            help_text text NULL CHECK (length(help_text) <= 2000),
            conditional_on_question_id uuid NULL,
            conditional_value jsonb NULL,
            prior_year_value jsonb NULL,
            linked_request_item_id uuid NULL,
            origin text NOT NULL CHECK (origin IN ('template', 'team', 'analytics',
                'fraud_inquiry', 'ssars_inquiry')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            sent_by uuid NULL,
            sent_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            CONSTRAINT questions_sent CHECK ((sent_by IS NULL) = (sent_at IS NULL)),
            FOREIGN KEY (tenant_id, questionnaire_id) REFERENCES questionnaires (tenant_id, id),
            FOREIGN KEY (tenant_id, section_id) REFERENCES questionnaire_sections (tenant_id, id),
            FOREIGN KEY (tenant_id, conditional_on_question_id)
                REFERENCES questions (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX questions_questionnaire ON questions (tenant_id, questionnaire_id, position)"
    )
    op.execute(
        """
        CREATE TABLE answer_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            question_id uuid NOT NULL,
            value jsonb NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            answered_by uuid NOT NULL,
            answered_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT answer_versions_one UNIQUE (tenant_id, question_id, version_no),
            FOREIGN KEY (tenant_id, question_id) REFERENCES questions (tenant_id, id)
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
    insert_columns(op, "questionnaire_templates", ("tenant_id", "name", "created_by"))
    op.execute("REVOKE UPDATE, DELETE ON questionnaire_templates FROM abacus_app")
    insert_columns(
        op,
        "questionnaire_template_versions",
        ("tenant_id", "template_id", "version", "content", "source_file_sha256", "imported_by"),
    )
    op.execute("REVOKE UPDATE, DELETE ON questionnaire_template_versions FROM abacus_app")
    op.execute(
        "GRANT UPDATE (published_by, published_at) ON questionnaire_template_versions "
        "TO abacus_app"
    )
    insert_columns(
        op,
        "questionnaires",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "request_list_id",
            "kind",
            "template_version_id",
            "title",
            "due_on",
            "addressed_to_contact_id",
            "data_class",
            "created_by",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON questionnaires FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, completed_by, completed_at, submitted_by, submitted_at, "
        "row_version) ON questionnaires TO abacus_app"
    )
    insert_columns(
        op,
        "questionnaire_sections",
        ("id", "tenant_id", "questionnaire_id", "name", "icon_key", "position"),
    )
    op.execute("REVOKE UPDATE, DELETE ON questionnaire_sections FROM abacus_app")
    insert_columns(
        op,
        "questions",
        (
            "id",
            "tenant_id",
            "questionnaire_id",
            "section_id",
            "question_key",
            "position",
            "type",
            "client_wording",
            "help_text",
            "conditional_on_question_id",
            "conditional_value",
            "prior_year_value",
            "linked_request_item_id",
            "origin",
            "created_by",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON questions FROM abacus_app")
    op.execute("GRANT UPDATE (sent_by, sent_at) ON questions TO abacus_app")
    insert_only(op, "answer_versions")
    insert_columns(
        op,
        "answer_versions",
        ("tenant_id", "question_id", "value", "version_no", "answered_by"),
    )
    op.execute(_LOCKED)
    op.execute(
        "CREATE TRIGGER answer_versions_locked BEFORE INSERT ON answer_versions "
        "FOR EACH ROW EXECUTE FUNCTION answer_versions_locked()"
    )
    op.execute(_IMMUTABLE)
    op.execute(
        "CREATE TRIGGER answer_versions_immutable BEFORE UPDATE OR DELETE ON answer_versions "
        "FOR EACH ROW EXECUTE FUNCTION answer_versions_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE answer_versions")
    op.execute("DROP FUNCTION answer_versions_locked()")
    op.execute("DROP FUNCTION answer_versions_immutable()")
    for table in reversed(_TABLES[:-1]):
        op.execute(f"DROP TABLE {table}")
