"""Practice quality management (Q-05-T05; SPEC-711 AC-1 to AC-10, AC-31; Q-05 §4.2; DEC-5611).
Expand-only, new tables only; the pipeline runs it after 8 pm CT inside the window (P-29).

Sixteen practice tables with forced RLS. The SQMS No. 1 register (`qm_settings`, `qm_cycles`,
`qm_objectives`, `qm_risks`, `qm_responses`, `qm_response_risks`), insert-only
`qm_register_imports` and human-only `qm_risk_assessment_reviews`, insert-only
`inspection_selection_rules`, `inspections` (an inspector is never the EP: a CHECK on the
snapshot and the `inspection_objectivity` trigger against the engagement's members, the EQR
included), `qm_findings` (agent-monitoring findings deduplicated per cycle and agent while open),
insert-only human-only `qm_finding_evaluations`, insert-only `qm_finding_links`,
`annual_evaluations` (status derived from the decision), and two rebuildable projections:
`agent_output_outcomes` (DEC-96: the one source for ADM-11 and INS-02) and
`draft_final_field_facts`. Free text is sealed (`*_sealed`, ADR-104 envelopes).

`inspections` is a QM record about the documentation, not part of it, so its rows carry no
engagement column the archive guard would bind (exemption noted for Q-05-T16's grants).

Revision ID: 0963
Revises: 0962
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0963"
down_revision = "0962"
branch_labels = None
depends_on = None

_ID = """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,"""
_KEYS = """
            UNIQUE (tenant_id, id)"""
_HUMAN = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)),"
)
_SEALED = "bytea NULL CHECK (octet_length({c}) <= 65536)"
_REF = "text NOT NULL CHECK ({c} ~ '^[A-Z][A-Z0-9-]{{1,19}}$')"
_COMPONENTS = (
    "('governance_leadership', 'ethical_requirements', 'acceptance_continuance', "
    "'engagement_performance', 'resources', 'information_communication')"
)

# (table, body, insert columns, update columns, insert-only)
TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    ("qm_settings", """
            ultimate_responsible_user_id uuid NOT NULL,
            operational_owner_user_id uuid NULL,
            evaluation_as_of_month_day text NOT NULL DEFAULT '12-15'
                CHECK (evaluation_as_of_month_day ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id),""",
     ("tenant_id", "ultimate_responsible_user_id", "operational_owner_user_id",
      "evaluation_as_of_month_day"),
     ("ultimate_responsible_user_id", "operational_owner_user_id", "evaluation_as_of_month_day",
      "updated_at"), False),
    ("qm_cycles", """
            year integer NOT NULL CHECK (year BETWEEN 2020 AND 2100),
            starts_on date NOT NULL,
            as_of date NOT NULL,
            CONSTRAINT qm_cycles_window CHECK (as_of > starts_on),
            UNIQUE (tenant_id, year),""",
     ("tenant_id", "year", "starts_on", "as_of"), (), False),
    ("qm_objectives", f"""
            component text NOT NULL CHECK (component IN {_COMPONENTS}),
            ref {_REF.format(c="ref")},
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
            owner_user_id uuid NULL,
            health_flag text NULL CHECK (health_flag IN ('at_risk')),
            note_sealed {_SEALED.format(c="note_sealed")},
            active boolean NOT NULL DEFAULT true,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (tenant_id, ref),""",
     ("tenant_id", "component", "ref", "title", "owner_user_id"),
     ("owner_user_id", "health_flag", "note_sealed", "active", "version"), False),
    ("qm_risks", f"""
            objective_id uuid NOT NULL,
            ref {_REF.format(c="ref")},
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
            UNIQUE (tenant_id, ref),
            FOREIGN KEY (tenant_id, objective_id) REFERENCES qm_objectives (tenant_id, id),""",
     ("tenant_id", "objective_id", "ref", "title"), ("title",), False),
    ("qm_responses", f"""
            objective_id uuid NOT NULL,
            ref {_REF.format(c="ref")},
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
            owner_user_id uuid NULL,
            frequency text NULL CHECK (frequency IN
                ('continuous', 'per_engagement', 'monthly', 'quarterly', 'annual')),
            UNIQUE (tenant_id, ref),
            FOREIGN KEY (tenant_id, objective_id) REFERENCES qm_objectives (tenant_id, id),""",
     ("tenant_id", "objective_id", "ref", "title", "owner_user_id", "frequency"),
     ("title", "owner_user_id", "frequency"), False),
    ("qm_response_risks", """
            response_id uuid NOT NULL,
            risk_id uuid NOT NULL,
            UNIQUE (response_id, risk_id),
            FOREIGN KEY (tenant_id, response_id) REFERENCES qm_responses (tenant_id, id),
            FOREIGN KEY (tenant_id, risk_id) REFERENCES qm_risks (tenant_id, id),""",
     ("tenant_id", "response_id", "risk_id"), (), False),
    ("qm_register_imports", """
            kind text NOT NULL CHECK (kind IN ('register', 'cycle')),
            source_evidence_version_id uuid NOT NULL,
            counts jsonb NOT NULL CHECK (jsonb_typeof(counts) = 'object'),
            status text NOT NULL CHECK (status IN ('dry_run', 'published')),
            published_by uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT qm_register_imports_publisher
                CHECK ((status = 'published') = (published_by IS NOT NULL)),""",
     ("tenant_id", "kind", "source_evidence_version_id", "counts", "status", "published_by"),
     (), True),
    ("qm_risk_assessment_reviews", f"""
            reviewed_on date NOT NULL,
            note_sealed {_SEALED.format(c="note_sealed")},
            reviewed_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN}""",
     ("tenant_id", "reviewed_on", "note_sealed", "reviewed_by"), (), True),
    ("inspection_selection_rules", """
            version integer NOT NULL CHECK (version >= 1),
            weights jsonb NOT NULL CHECK (jsonb_typeof(weights) = 'object'),
            seed bigint NOT NULL,
            created_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, version),""",
     ("tenant_id", "version", "weights", "seed", "created_by"), (), True),
    ("inspections", f"""
            cycle_id uuid NOT NULL,
            ref {_REF.format(c="ref")},
            work_item_id uuid NOT NULL,
            inspected_engagement_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN
                ('post_issuance_archived', 'pre_lock', 'in_process', 'post_filing')),
            basis text NOT NULL CHECK (basis IN ('sqms1', 'firm_policy_c230_10_36')),
            ep_signer_user_id uuid NOT NULL,
            inspector_user_id uuid NOT NULL,
            selected_because text NULL CHECK (char_length(selected_because) <= 300),
            risk_score numeric(6, 2) NULL CHECK (risk_score >= 0),
            rule_version integer NULL CHECK (rule_version >= 1),
            due_on date NULL,
            status text NOT NULL DEFAULT 'planned'
                CHECK (status IN ('planned', 'in_progress', 'concluded')),
            concluded_on date NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            CONSTRAINT inspections_not_ep CHECK (inspector_user_id <> ep_signer_user_id),
            CONSTRAINT inspections_concluded
                CHECK ((status = 'concluded') = (concluded_on IS NOT NULL)),
            UNIQUE (tenant_id, ref),
            FOREIGN KEY (tenant_id, cycle_id) REFERENCES qm_cycles (tenant_id, id),""",
     ("tenant_id", "cycle_id", "ref", "work_item_id", "inspected_engagement_id", "kind", "basis",
      "ep_signer_user_id", "inspector_user_id", "selected_because", "risk_score", "rule_version",
      "due_on"),
     ("inspector_user_id", "due_on", "status", "concluded_on", "version"), False),
    ("qm_findings", f"""
            cycle_id uuid NOT NULL,
            ref {_REF.format(c="ref")},
            inspection_id uuid NULL,
            source text NOT NULL CHECK (source IN ('inspection', 'agent_monitoring', 'other')),
            agent_key text NULL CHECK (agent_key ~ '^[a-z][a-z0-9_.]{{0,79}}$'),
            title_sealed bytea NOT NULL CHECK (octet_length(title_sealed) <= 4096),
            root_cause_category text NULL CHECK (root_cause_category IN
                ('people', 'process', 'methodology', 'technology', 'culture')),
            root_cause_sealed {_SEALED.format(c="root_cause_sealed")},
            remediation_sealed {_SEALED.format(c="remediation_sealed")},
            owner_user_id uuid NULL,
            due_on date NULL,
            status text NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'remediated')),
            remediated_at timestamptz NULL,
            remediation_note_sealed {_SEALED.format(c="remediation_note_sealed")},
            raised_by_kind text NOT NULL CHECK (raised_by_kind IN ('human', 'system')),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            CONSTRAINT qm_findings_agent
                CHECK ((source = 'agent_monitoring') = (agent_key IS NOT NULL)),
            CONSTRAINT qm_findings_inspection
                CHECK (source <> 'inspection' OR inspection_id IS NOT NULL),
            CONSTRAINT qm_findings_remediated
                CHECK ((status = 'remediated') = (remediated_at IS NOT NULL)),
            UNIQUE (tenant_id, ref),
            FOREIGN KEY (tenant_id, cycle_id) REFERENCES qm_cycles (tenant_id, id),
            FOREIGN KEY (tenant_id, inspection_id) REFERENCES inspections (tenant_id, id),""",
     ("tenant_id", "cycle_id", "ref", "inspection_id", "source", "agent_key", "title_sealed",
      "owner_user_id", "due_on", "raised_by_kind"),
     ("root_cause_category", "root_cause_sealed", "remediation_sealed", "owner_user_id", "due_on",
      "status", "remediated_at", "remediation_note_sealed", "version"), False),
    ("qm_finding_evaluations", f"""
            finding_id uuid NOT NULL,
            evaluation text NOT NULL CHECK (evaluation IN ('finding_open', 'not_a_deficiency',
                'deficiency', 'severe_deficiency', 'severe_and_pervasive')),
            rationale_sealed bytea NOT NULL CHECK (octet_length(rationale_sealed) <= 65536),
            evaluated_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN}
            FOREIGN KEY (tenant_id, finding_id) REFERENCES qm_findings (tenant_id, id),""",
     ("tenant_id", "finding_id", "evaluation", "rationale_sealed", "evaluated_by"), (), True),
    ("qm_finding_links", """
            finding_id uuid NOT NULL,
            link_kind text NOT NULL CHECK (link_kind IN ('methodology_step_version',
                'post_issuance_event', 'work_item', 'todo', 'agent_run')),
            ref jsonb NOT NULL CHECK (jsonb_typeof(ref) = 'object'),
            created_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES qm_findings (tenant_id, id),""",
     ("tenant_id", "finding_id", "link_kind", "ref", "created_by"), (), True),
    ("annual_evaluations", """
            cycle_id uuid NOT NULL UNIQUE,
            responsible_user_id uuid NOT NULL,
            decision_card_id uuid NULL,
            root_cause_reviewed_at timestamptz NULL,
            root_cause_reviewed_by uuid NULL,
            memo_evidence_version_id uuid NULL,
            checklist jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(checklist) = 'object'),
            CONSTRAINT annual_evaluations_review
                CHECK ((root_cause_reviewed_at IS NULL) = (root_cause_reviewed_by IS NULL)),
            FOREIGN KEY (tenant_id, cycle_id) REFERENCES qm_cycles (tenant_id, id),""",
     ("tenant_id", "cycle_id", "responsible_user_id"),
     ("decision_card_id", "root_cause_reviewed_at", "root_cause_reviewed_by",
      "memo_evidence_version_id", "checklist"), False),
    ("agent_output_outcomes", """
            source_kind text NOT NULL CHECK (source_kind IN ('review_decision', 'suggestion',
                'proposal', 'checkpoint', 'proposed_entry')),
            source_id uuid NOT NULL,
            agent_key text NOT NULL CHECK (agent_key ~ '^[a-z][a-z0-9_.]{0,79}$'),
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            office_id uuid NULL,
            service_line text NULL CHECK (service_line IN ('audit', 'tax', 'cas', 'advisory')),
            outcome text NOT NULL CHECK (outcome IN ('adopted', 'changed', 'rejected')),
            reason_code text NULL CHECK (reason_code ~ '^[a-z][a-z0-9_]{0,39}$'),
            decided_at timestamptz NOT NULL,
            decided_by uuid NULL,
            source_event_id uuid NOT NULL UNIQUE,
            UNIQUE (tenant_id, source_kind, source_id),""",
     ("tenant_id", "source_kind", "source_id", "agent_key", "engagement_id", "work_item_id",
      "office_id", "service_line", "outcome", "reason_code", "decided_at", "decided_by",
      "source_event_id"),
     ("outcome", "reason_code", "decided_at", "decided_by"), False),
    ("draft_final_field_facts", """
            return_id uuid NOT NULL,
            field_class text NOT NULL CHECK (field_class ~ '^[a-z][a-z0-9_.]{0,79}$'),
            office_id uuid NULL,
            agent_drafted boolean NOT NULL,
            changed_before_filing boolean NOT NULL,
            filed_at timestamptz NOT NULL,
            UNIQUE (tenant_id, return_id, field_class),""",
     ("tenant_id", "return_id", "field_class", "office_id", "agent_drafted",
      "changed_before_filing", "filed_at"),
     ("agent_drafted", "changed_before_filing", "filed_at"), False),
)  # fmt: skip


def _immutable(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_immutable()"
    )


def upgrade() -> None:
    for table, body, _ins, _upd, _io in TABLES:
        op.execute(f"CREATE TABLE {table} ({_ID}{body}{_KEYS}\n        )")
    # Q-05 §4.2: one open agent-monitoring finding per cycle and agent (the nightly job's dedupe).
    op.execute(
        "CREATE UNIQUE INDEX qm_findings_agent_open ON qm_findings "
        "(tenant_id, cycle_id, agent_key) "
        "WHERE source = 'agent_monitoring' AND status <> 'remediated'"
    )
    op.execute(
        "CREATE INDEX agent_output_outcomes_window ON agent_output_outcomes "
        "(tenant_id, agent_key, decided_at)"
    )
    for table, _body, ins, upd, io in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, list(ins))
        if io:
            insert_only(op, table)
            _immutable(table)
        else:
            op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
            if upd:
                op.execute(f"GRANT UPDATE ({', '.join(upd)}) ON {table} TO abacus_app")
    # The projections are rebuildable: the rebuild command deletes and replays (Q-05-T07).
    for table in ("agent_output_outcomes", "draft_final_field_facts"):
        op.execute(f"GRANT DELETE ON {table} TO abacus_app")
    # AC-7: an inspector is never a member of the inspected engagement, the EQR included.
    op.execute(
        """
        CREATE FUNCTION inspection_objectivity() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM engagement_members m
                WHERE m.tenant_id = NEW.tenant_id
                  AND m.engagement_id = NEW.inspected_engagement_id
                  AND m.user_id = NEW.inspector_user_id
            ) THEN
                RAISE EXCEPTION 'inspector_not_objective' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER inspection_objectivity BEFORE INSERT OR UPDATE OF inspector_user_id "
        "ON inspections FOR EACH ROW EXECUTE FUNCTION inspection_objectivity()"
    )


def downgrade() -> None:
    for table, _body, _ins, _upd, _io in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION inspection_objectivity()")
    for table, _body, _ins, _upd, io in TABLES:
        if io:
            op.execute(f"DROP FUNCTION {table}_immutable()")
