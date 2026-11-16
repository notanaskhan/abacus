"""A-09-T12 (S46; TASK-8093; SPEC-658; SAS 149 / AU-C 600; amber): `assurance_group`, expand-only.

The group audit's own records (AUD-34, AUD-35, POR-23):

- `components`: each consolidation entity's planned work (`full_scope`, `specific_procedures`,
  `analytical_only`), scope areas, who performs it (the group team or a component auditor) and
  the component PM. An analytical-only component has no PM; a component auditor performs the
  work exactly when one is named.
- `component_auditors`: the other firm (organisation, city, its engagement-partner contact of kind
  `component_auditor`), the component it audits, and the SAS 149 evaluations (questionnaire,
  competence by a person, independence, peer review, make-reference).
- `component_instructions` (`draft`, `sent`, `acknowledged`) with insert-only
  `component_instruction_versions` (sections, the generated document, the drafting run, hash).
- `component_milestones` (instructions acknowledged, interim memo, clearance, summary of
  uncorrected misstatements) and `component_deliverables` (`expected`, `received`, `reviewed`;
  Late is derived, never stored), with the return fields; a review is a person's only.
- `materiality_versions` gains `scope` (`entity`, default, or `group`) and `consolidation_id`:
  a group version names its consolidation, an entity version none.

Revision ID: 0898
Revises: 0897
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0898"
down_revision = "0897"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_SCOPE_COLS = ("tenant_id", "engagement_id", "work_item_id")
TABLES = (
    "component_milestones",
    "component_deliverables",
    "component_instruction_versions",
    "component_instructions",
    "component_auditors",
    "components",
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE components (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            consolidation_entity_id uuid NOT NULL,
            planned_work text NOT NULL
                CHECK (planned_work IN ('full_scope', 'specific_procedures', 'analytical_only')),
            scope_areas text[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(scope_areas) <= 20),
            performed_by text NOT NULL CHECK (performed_by IN ('group_team', 'component_auditor')),
            component_auditor_id uuid NULL,
            component_pm numeric(20, 2) NULL CHECK (component_pm > 0),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, consolidation_entity_id),
            -- AC: a PM on an Analytical-only component is refused.
            CONSTRAINT components_analytical_no_pm
                CHECK (planned_work <> 'analytical_only' OR component_pm IS NULL),
            CONSTRAINT components_performer
                CHECK ((performed_by = 'component_auditor') = (component_auditor_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, consolidation_entity_id)
                REFERENCES consolidation_entities (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE component_auditors (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            organisation_name text NOT NULL
                CHECK (length(btrim(organisation_name)) BETWEEN 1 AND 200),
            city text NULL CHECK (length(city) <= 120),
            ep_contact_id uuid NULL,
            component_id uuid NULL,
            questionnaire_received_on date NULL,
            competence_evaluated_by uuid NULL,
            competence_evaluated_at timestamptz NULL,
            independence_confirmed_at timestamptz NULL,
            peer_review_obtained_on date NULL,
            make_reference boolean NOT NULL DEFAULT false,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((competence_evaluated_by IS NULL) = (competence_evaluated_at IS NULL)),
            FOREIGN KEY (tenant_id, ep_contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, component_id) REFERENCES components (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "ALTER TABLE components ADD CONSTRAINT components_auditor_fk FOREIGN KEY "
        "(tenant_id, component_auditor_id) REFERENCES component_auditors (tenant_id, id)"
    )
    op.execute(
        f"""
        CREATE TABLE component_instructions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            component_auditor_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'sent', 'acknowledged')),
            current_version_id uuid NULL,
            sent_by uuid NULL,
            sent_at timestamptz NULL,
            sent_actor_kind text NULL CHECK (sent_actor_kind = 'human'),
            acknowledged_contact_id uuid NULL,
            acknowledged_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, component_auditor_id),
            CONSTRAINT component_instructions_sent CHECK (
                (status = 'draft') = (sent_at IS NULL)
                AND (sent_at IS NULL OR (sent_by IS NOT NULL AND sent_actor_kind = 'human'))
            ),
            CONSTRAINT component_instructions_acknowledged
                CHECK ((status = 'acknowledged') = (acknowledged_at IS NOT NULL)),
            FOREIGN KEY (tenant_id, component_auditor_id)
                REFERENCES component_auditors (tenant_id, id),
            FOREIGN KEY (tenant_id, acknowledged_contact_id)
                REFERENCES contacts (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE component_instruction_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            instructions_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            sections jsonb NOT NULL CHECK (jsonb_typeof(sections) = 'array'),
            generated_document_id uuid NULL,
            drafted_by_run_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{{64}}$'),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, instructions_id, version_no),
            FOREIGN KEY (tenant_id, instructions_id)
                REFERENCES component_instructions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "ALTER TABLE component_instructions ADD CONSTRAINT component_instructions_version_fk "
        "FOREIGN KEY (tenant_id, current_version_id) "
        "REFERENCES component_instruction_versions (tenant_id, id)"
    )
    op.execute(
        f"""
        CREATE TABLE component_deliverables (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            component_auditor_id uuid NOT NULL,
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
            due_on date NOT NULL,
            status text NOT NULL DEFAULT 'expected'
                CHECK (status IN ('expected', 'received', 'reviewed')),
            received_at timestamptz NULL,
            evidence_item_id uuid NULL,
            reviewed_by uuid NULL,
            reviewed_at timestamptz NULL,
            reviewed_actor_kind text NULL,
            returned_at timestamptz NULL,
            return_reason text NULL CHECK (length(return_reason) BETWEEN 1 AND 1000),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- AC: a deliverable review by a non-human actor is refused.
            CONSTRAINT component_deliverables_human_review
                CHECK (reviewed_actor_kind IS NULL OR reviewed_actor_kind = 'human'),
            CONSTRAINT component_deliverables_reviewed CHECK (
                (status = 'reviewed') = (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
                                          AND reviewed_actor_kind IS NOT NULL)
            ),
            CONSTRAINT component_deliverables_received
                CHECK (status = 'expected' OR received_at IS NOT NULL),
            CONSTRAINT component_deliverables_return
                CHECK ((returned_at IS NULL) = (return_reason IS NULL)),
            FOREIGN KEY (tenant_id, component_auditor_id)
                REFERENCES component_auditors (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_item_id)
                REFERENCES evidence_items (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE component_milestones (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            component_auditor_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('instructions_acknowledged', 'interim_memo',
                'clearance_letter', 'summary_of_uncorrected_misstatements', 'other')),
            label text NULL CHECK (length(label) BETWEEN 1 AND 200),
            due_on date NOT NULL,
            deliverable_id uuid NULL,
            position smallint NOT NULL DEFAULT 0 CHECK (position >= 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (kind <> 'other' OR label IS NOT NULL),
            FOREIGN KEY (tenant_id, component_auditor_id)
                REFERENCES component_auditors (tenant_id, id),
            FOREIGN KEY (tenant_id, deliverable_id)
                REFERENCES component_deliverables (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    for table in TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(
        op, "components",
        (*_SCOPE_COLS, "consolidation_entity_id", "planned_work", "scope_areas", "performed_by",
         "component_auditor_id", "component_pm", "created_by"),
    )  # fmt: skip
    op.execute(
        "GRANT UPDATE (planned_work, scope_areas, performed_by, component_auditor_id, "
        "component_pm, row_version) ON components TO abacus_app"
    )
    insert_columns(
        op, "component_auditors",
        (*_SCOPE_COLS, "organisation_name", "city", "ep_contact_id", "component_id", "created_by"),
    )  # fmt: skip
    op.execute(
        "GRANT UPDATE (organisation_name, city, ep_contact_id, component_id, "
        "questionnaire_received_on, competence_evaluated_by, competence_evaluated_at, "
        "independence_confirmed_at, peer_review_obtained_on, make_reference, row_version) "
        "ON component_auditors TO abacus_app"
    )
    insert_columns(op, "component_instructions", (*_SCOPE_COLS, "component_auditor_id"))
    op.execute(
        "GRANT UPDATE (status, current_version_id, sent_by, sent_at, sent_actor_kind, "
        "acknowledged_contact_id, acknowledged_at, row_version) ON component_instructions "
        "TO abacus_app"
    )
    insert_columns(
        op, "component_instruction_versions",
        (*_SCOPE_COLS, "instructions_id", "version_no", "sections", "generated_document_id",
         "drafted_by_run_id", "content_hash", "created_by"),
    )  # fmt: skip
    insert_only(op, "component_instruction_versions")
    insert_columns(
        op, "component_deliverables",
        (*_SCOPE_COLS, "component_auditor_id", "title", "due_on"),
    )  # fmt: skip
    op.execute(
        "GRANT UPDATE (status, received_at, evidence_item_id, reviewed_by, reviewed_at, "
        "reviewed_actor_kind, returned_at, return_reason, row_version) "
        "ON component_deliverables TO abacus_app"
    )
    insert_columns(
        op, "component_milestones",
        (*_SCOPE_COLS, "component_auditor_id", "kind", "label", "due_on", "deliverable_id",
         "position"),
    )  # fmt: skip
    op.execute(
        "GRANT UPDATE (due_on, deliverable_id, position) ON component_milestones TO abacus_app"
    )
    op.execute(
        """
        ALTER TABLE materiality_versions
            ADD COLUMN scope text NOT NULL DEFAULT 'entity'
                CONSTRAINT materiality_versions_scope CHECK (scope IN ('entity', 'group')),
            ADD COLUMN consolidation_id uuid NULL,
            ADD CONSTRAINT materiality_versions_consolidation_fk
                FOREIGN KEY (tenant_id, consolidation_id)
                REFERENCES consolidations (tenant_id, id),
            ADD CONSTRAINT materiality_versions_group_names_consolidation
                CHECK ((scope = 'group') = (consolidation_id IS NOT NULL))
        """
    )
    op.execute("GRANT INSERT (scope, consolidation_id) ON materiality_versions TO abacus_app")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE materiality_versions "
        "DROP CONSTRAINT materiality_versions_group_names_consolidation, "
        "DROP CONSTRAINT materiality_versions_consolidation_fk, DROP COLUMN consolidation_id, "
        "DROP COLUMN scope"
    )
    op.execute(
        "ALTER TABLE component_instructions DROP CONSTRAINT component_instructions_version_fk"
    )
    op.execute("ALTER TABLE components DROP CONSTRAINT components_auditor_fk")
    for table in TABLES:
        op.execute(f"DROP TABLE {table}")
