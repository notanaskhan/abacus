"""A-05 M6: EBP investments and Form 5500 (A-05-T35; A-05 §4.2 M6; EBP-06, EBP-07; DEC-2234;
expand-only).

On the EBP audit's work item, tenant-scoped with forced RLS:
- `ebp_trust_report_lines`: the certified Summary of Net Trust Assets lines (fund, beginning and
  end of year, fair-value level), each cited, adopted from a proposal or keyed by a person.
- `ebp_certification_points` (one per point) and insert-only `ebp_certification_evaluations`:
  the 29 CFR 2520.103-8 points; **an evaluation is a person's act** (the row's actor is the
  transaction's own and human), never the agent's.
- `ebp_form5500_drafts` (the TPA's draft), `ebp_form5500_lines` (code's tie of each Schedule H
  line to the FS caption: tie, reconciling item or inconsistent; an agent's classification stays
  a suggestion until a person adopts it), `ebp_part_iv_answers` (4a to 4m against the audit) and
  `ebp_supplemental_schedules` (4i and 4a rows, rendered through C11).
- `ebp_schedule_h_mappings`: the firm's FS-caption → Schedule H line map (firm content loaded
  through an admin import, versioned by plan year; OQ-5).

Revision ID: 0665
Revises: 0664
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0665"
down_revision = "0664"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_MONEY = "numeric(18,2)"
_STAMPS = """
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),"""
_ORIGIN = "origin text NOT NULL CHECK (origin IN ('agent_proposal', 'keyed', 'import'))"
_EVIDENCE_FK = """
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),"""
_TABLES = (
    "ebp_trust_report_lines",
    "ebp_certification_points",
    "ebp_certification_evaluations",
    "ebp_form5500_drafts",
    "ebp_form5500_lines",
    "ebp_part_iv_answers",
    "ebp_supplemental_schedules",
    "ebp_schedule_h_mappings",
)
INSERTS: dict[str, tuple[str, ...]] = {
    "ebp_trust_report_lines": (
        "tenant_id", "engagement_id", "work_item_id", "evidence_version_id", "line_key",
        "fund_name", "boy", "eoy", "fair_value_level", "citation_id", "origin",
    ),
    "ebp_certification_points": (
        "tenant_id", "engagement_id", "work_item_id", "evidence_version_id", "point_key",
        "proposed_answer", "citation_id",
    ),
    "ebp_certification_evaluations": (
        "tenant_id", "engagement_id", "work_item_id", "point_id", "answer", "note",
        "actor_kind", "actor_id",
    ),
    "ebp_form5500_drafts": (
        "tenant_id", "engagement_id", "work_item_id", "evidence_version_id", "received_at",
        "plan_year", "preparer_provider_id", "status",
    ),
    "ebp_form5500_lines": (
        "tenant_id", "engagement_id", "work_item_id", "draft_id", "line_code", "caption",
        "fs_amount", "f5500_amount", "difference", "classification", "note_ref",
        "f5500_citation_id", "fs_ref", "classified_by_kind", "engine_version", "inputs_hash",
    ),
    "ebp_part_iv_answers": (
        "tenant_id", "engagement_id", "work_item_id", "draft_id", "question", "draft_answer",
        "amount", "evidence_ref", "result", "issue_id",
    ),
    "ebp_supplemental_schedules": (
        "tenant_id", "engagement_id", "work_item_id", "kind", "rows", "total",
        "generated_document_id", "engine_version", "inputs_hash",
    ),
    "ebp_schedule_h_mappings": (
        "tenant_id", "version", "fs_caption_key", "schedule_h_line", "effective_plan_year",
        "published_at", "published_by",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "ebp_trust_report_lines": ("superseded_by", "version", "updated_at"),
    "ebp_certification_points": ("proposed_answer", "citation_id", "version", "updated_at"),
    "ebp_form5500_drafts": ("status", "version", "updated_at"),
    "ebp_form5500_lines": (
        "fs_amount", "f5500_amount", "difference", "classification", "note_ref", "fs_ref",
        "classified_by_kind", "engine_version", "inputs_hash", "version", "updated_at",
    ),
    "ebp_part_iv_answers": ("draft_answer", "amount", "evidence_ref", "result", "issue_id",
                            "version", "updated_at"),
    "ebp_supplemental_schedules": (
        "rows", "total", "generated_document_id", "engine_version", "inputs_hash", "version",
        "updated_at",
    ),
}  # fmt: skip

_IMMUTABLE = """
    CREATE FUNCTION ebp_certification_evaluations_immutable() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        RAISE EXCEPTION 'certification evaluations are insert-only'
            USING ERRCODE = 'insufficient_privilege';
    END $$
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE ebp_trust_report_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            evidence_version_id uuid NOT NULL,
            line_key text NOT NULL CHECK (line_key ~ '^[a-z0-9_.-]{{1,80}}$'),
            fund_name text NOT NULL CHECK (char_length(fund_name) BETWEEN 1 AND 200),
            boy {_MONEY} NULL,
            eoy {_MONEY} NULL,
            fair_value_level text NOT NULL
                CHECK (fair_value_level IN ('level1', 'nav', 'not_certified')),
            citation_id uuid NOT NULL,
            {_ORIGIN},
            superseded_by uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            CHECK (boy IS NOT NULL OR eoy IS NOT NULL),
            FOREIGN KEY (tenant_id, superseded_by)
                REFERENCES ebp_trust_report_lines (tenant_id, id),{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ebp_trust_report_lines_current ON ebp_trust_report_lines "
        "(tenant_id, work_item_id, evidence_version_id, line_key) WHERE superseded_by IS NULL"
    )
    op.execute(
        f"""
        CREATE TABLE ebp_certification_points (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            evidence_version_id uuid NOT NULL,
            point_key text NOT NULL CHECK (point_key IN ('qualifying_institution',
                'complete_and_accurate', 'period', 'signer_and_date', 'covers', 'not_covered')),
            proposed_answer text NULL CHECK (char_length(proposed_answer) <= 500),
            citation_id uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, evidence_version_id, point_key),
            CHECK (proposed_answer IS NULL OR citation_id IS NOT NULL),{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_certification_evaluations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            point_id uuid NOT NULL,
            answer text NOT NULL CHECK (answer IN ('evaluated', 'not_evaluated')),
            note text NULL CHECK (char_length(note) <= 1000),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true),
            actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT ebp_certification_evaluations_by_a_person CHECK (actor_kind = 'human'
                AND actor_kind = current_setting('app.actor_kind', true)
                AND actor_id = current_setting('app.actor_id', true)),
            FOREIGN KEY (tenant_id, point_id)
                REFERENCES ebp_certification_points (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_form5500_drafts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            evidence_version_id uuid NOT NULL,
            received_at timestamptz NOT NULL,
            plan_year integer NOT NULL CHECK (plan_year BETWEEN 2000 AND 2100),
            preparer_provider_id uuid NULL,
            status text NOT NULL DEFAULT 'received'
                CHECK (status IN ('received', 'tied', 'superseded')),{_STAMPS}
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, preparer_provider_id)
                REFERENCES ebp_service_providers (tenant_id, id),{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ebp_form5500_drafts_current ON ebp_form5500_drafts "
        "(tenant_id, work_item_id, plan_year) WHERE status <> 'superseded'"
    )
    op.execute(
        f"""
        CREATE TABLE ebp_form5500_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            draft_id uuid NOT NULL,
            line_code text NOT NULL CHECK (line_code ~ '^[0-9a-z()]{{1,20}}$'),
            caption text NOT NULL CHECK (char_length(caption) BETWEEN 1 AND 200),
            fs_amount {_MONEY} NULL,
            f5500_amount {_MONEY} NULL,
            difference {_MONEY} NULL,
            classification text NULL
                CHECK (classification IN ('tie', 'reconciling_item', 'inconsistent')),
            note_ref text NULL CHECK (char_length(note_ref) <= 40),
            f5500_citation_id uuid NULL,
            fs_ref jsonb NULL CHECK (fs_ref IS NULL OR jsonb_typeof(fs_ref) = 'object'),
            classified_by_kind text NULL CHECK (classified_by_kind IN ('code', 'human')),
            engine_version text NULL CHECK (char_length(engine_version) <= 40),
            inputs_hash text NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, draft_id, line_code),
            CHECK (difference IS NULL OR inputs_hash IS NOT NULL),
            CHECK (classification IS NULL OR classified_by_kind IS NOT NULL),
            CHECK (classification IS DISTINCT FROM 'reconciling_item' OR note_ref IS NOT NULL),
            FOREIGN KEY (tenant_id, draft_id)
                REFERENCES ebp_form5500_drafts (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_part_iv_answers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            draft_id uuid NOT NULL,
            question text NOT NULL CHECK (question ~ '^4[a-m]$'),
            draft_answer text NULL CHECK (draft_answer IN ('yes', 'no', 'na')),
            amount {_MONEY} NULL,
            evidence_ref jsonb NULL CHECK (evidence_ref IS NULL
                OR jsonb_typeof(evidence_ref) = 'object'),
            result text NULL CHECK (result IN ('consistent', 'inconsistent')),
            issue_id uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, draft_id, question),
            CHECK (result IS DISTINCT FROM 'inconsistent' OR issue_id IS NOT NULL),
            FOREIGN KEY (tenant_id, draft_id)
                REFERENCES ebp_form5500_drafts (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_supplemental_schedules (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            kind text NOT NULL CHECK (kind IN ('4i', '4a')),
            rows jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(rows) = 'array'),
            total {_MONEY} NULL,
            generated_document_id uuid NULL,
            engine_version text NULL CHECK (char_length(engine_version) <= 40),
            inputs_hash text NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, kind),
            CHECK (total IS NULL OR inputs_hash IS NOT NULL),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        """
        CREATE TABLE ebp_schedule_h_mappings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            version integer NOT NULL CHECK (version >= 1),
            fs_caption_key text NOT NULL CHECK (fs_caption_key ~ '^[a-z0-9_.-]{1,80}$'),
            schedule_h_line text NOT NULL CHECK (schedule_h_line ~ '^[0-9a-z()]{1,20}$'),
            effective_plan_year integer NOT NULL CHECK (effective_plan_year BETWEEN 2000 AND 2100),
            published_at timestamptz NULL,
            published_by uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version, fs_caption_key),
            CHECK ((published_at IS NULL) = (published_by IS NULL))
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERTS[table])
        if table in UPDATES:
            op.execute(f"GRANT UPDATE ({', '.join(UPDATES[table])}) ON {table} TO abacus_app")
    for table in ("ebp_certification_evaluations", "ebp_schedule_h_mappings"):
        insert_only(op, table)
    op.execute(_IMMUTABLE)
    op.execute("REVOKE ALL ON FUNCTION ebp_certification_evaluations_immutable() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER ebp_certification_evaluations_immutable BEFORE UPDATE OR DELETE "
        "ON ebp_certification_evaluations FOR EACH ROW "
        "EXECUTE FUNCTION ebp_certification_evaluations_immutable()"
    )
    op.execute(
        "CREATE TRIGGER ebp_certification_evaluations_no_truncate BEFORE TRUNCATE "
        "ON ebp_certification_evaluations FOR EACH STATEMENT "
        "EXECUTE FUNCTION ebp_certification_evaluations_immutable()"
    )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION ebp_certification_evaluations_immutable()")
