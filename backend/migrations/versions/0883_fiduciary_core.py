"""T-07-T07 (S44; TASK-8021; T-07 §4.2 M1; SPEC-656 AC-15.5; DEC-5010): `fiduciary_core`,
expand-only, in `tax`.

- `trust_profiles` (one per trust or estate client entity; its facts update in place).
- The instrument: `governing_instruments` (an amendment is a new row that supersedes the old one),
  `instrument_segmentations` and `instrument_clauses` (no clause text: labels, pages, regions
  and a text hash; the face re-reads the sealed layer), all insert-only.
- The interpretation: `instrument_interpretations` (status forward-only, except
  `approved → reopened → proposed | adopted`; one current per return), and
  `instrument_determinations` with insert-only `instrument_determination_versions` (a clause
  citation for the five clause-governed keys; a reason on every human change after the first;
  no version while the interpretation is approved: `interpretation_locked`).
- The calculation's inputs, each a parent with insert-only versions: `fai_lines` (≥ 1
  citation), `trust_expenses`, `trust_distributions`.
- The calculation: insert-only `fai_dni_computations` (engine, version, inputs hash, parameter
  set; signed status is computed from `sign_offs`) and `beneficiary_allocations` (Σ DNI
  allocated = the income distribution deduction, a deferred constraint trigger).
- `sixty_five_day_elections`: insert-only, latest wins, `actor_kind = 'human'` by CHECK.

Parents are insert-only too: the current version is the latest `seq` (no pointer to update).
Forced RLS on every table through `tenant_table()`. Classification (ADR-031): every return
value is TRI (`restricted`, §7216); free text that names a beneficiary, a settlor or a reason is
sealed (`*_sealed`, `bytea`); money is `numeric(18,2)`, shares `numeric(9,6)`.

Revision ID: 0883
Revises: 0882
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0883"
down_revision = "0882"
branch_labels = None
depends_on = None

_MONEY = "numeric(18,2)"
_SHA = "~ '^[0-9a-f]{64}$'"
_KEYS = (
    "('grantor_status', 'trust_type', 'fai_definition', 'trustee_fees', 'principal_invaded', "
    "'exemption', 'election_65_day')"
)
_GOVERNED = (
    "('grantor_status', 'trust_type', 'fai_definition', 'trustee_fees', 'principal_invaded')"
)
_RETURN_FK = (
    "FOREIGN KEY (tenant_id, engagement_id, work_item_id) "
    "REFERENCES work_items (tenant_id, engagement_id, id)"
)
_RETURN_COLS = "engagement_id uuid NOT NULL, work_item_id uuid NOT NULL"
_SET_BY = (
    "set_by_kind text NOT NULL CHECK (set_by_kind IN ('agent', 'human')), "
    "set_by_id uuid NOT NULL, "
    "reason_sealed bytea NULL CHECK (octet_length(reason_sealed) BETWEEN 1 AND 8192)"
)

TABLES = (
    "trust_profiles",
    "governing_instruments",
    "instrument_segmentations",
    "instrument_clauses",
    "instrument_interpretations",
    "instrument_determinations",
    "instrument_determination_versions",
    "fai_lines",
    "fai_line_versions",
    "trust_expenses",
    "trust_expense_versions",
    "trust_distributions",
    "trust_distribution_versions",
    "fai_dni_computations",
    "beneficiary_allocations",
    "sixty_five_day_elections",
)


def _lock_down(table: str, inserts: tuple[str, ...], updates: tuple[str, ...] = ()) -> None:
    tenant_table(op, table)
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(op, table, inserts)
    if updates:
        op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
    else:
        insert_only(op, table)


def _tables() -> None:
    op.execute(
        """
        CREATE TABLE trust_profiles (
            client_entity_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            fiduciary_kind text NOT NULL CHECK (fiduciary_kind IN ('trust', 'estate')),
            agreement_date date NULL,
            revocable boolean NOT NULL DEFAULT false,
            irrevocable_since date NULL,
            settlor_name_sealed bytea NULL CHECK (octet_length(settlor_name_sealed) <= 1024),
            settlor_died_year integer NULL CHECK (settlor_died_year BETWEEN 1900 AND 2100),
            remainder_sealed bytea NULL CHECK (octet_length(remainder_sealed) <= 2048),
            residency_state char(2) NULL CHECK (residency_state ~ '^[A-Z]{2}$'),
            residency_basis text NULL CHECK (length(residency_basis) <= 200),
            state_form text NULL CHECK (length(state_form) <= 20),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, client_entity_id),
            CHECK (NOT revocable OR irrevocable_since IS NULL),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE governing_instruments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            supersedes_instrument_id uuid NULL,
            attached_by uuid NOT NULL,
            attached_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_entity_id, evidence_version_id),
            CHECK (supersedes_instrument_id IS DISTINCT FROM id),
            FOREIGN KEY (tenant_id, client_entity_id)
                REFERENCES trust_profiles (tenant_id, client_entity_id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, supersedes_instrument_id)
                REFERENCES governing_instruments (tenant_id, id),
            FOREIGN KEY (tenant_id, attached_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE instrument_segmentations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            instrument_id uuid NOT NULL,
            segmentation_version text NOT NULL CHECK (segmentation_version ~ '^[0-9]+\\.[0-9]+$'),
            text_source text NOT NULL CHECK (text_source IN ('text_layer', 'ocr')),
            status text NOT NULL CHECK (status IN ('segmented', 'needs_review')),
            confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
            clause_count integer NOT NULL CHECK (clause_count >= 0),
            layer_sha256 text NOT NULL CHECK (layer_sha256 {_SHA}),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, instrument_id) REFERENCES governing_instruments (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE instrument_clauses (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            segmentation_id uuid NOT NULL,
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 40),
            heading text NULL CHECK (length(heading) <= 200),
            ordinal integer NOT NULL CHECK (ordinal >= 0),
            parent_clause_id uuid NULL,
            page_from integer NOT NULL CHECK (page_from >= 1),
            page_to integer NOT NULL,
            regions jsonb NOT NULL CHECK (jsonb_typeof(regions) = 'array'
                AND jsonb_array_length(regions) BETWEEN 1 AND 50),
            text_sha256 text NOT NULL CHECK (text_sha256 {_SHA}),
            marked_by uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (segmentation_id, label),
            CHECK (page_to >= page_from),
            FOREIGN KEY (tenant_id, segmentation_id)
                REFERENCES instrument_segmentations (tenant_id, id),
            FOREIGN KEY (tenant_id, parent_clause_id)
                REFERENCES instrument_clauses (tenant_id, id),
            FOREIGN KEY (tenant_id, marked_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE instrument_interpretations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_RETURN_COLS},
            instrument_id uuid NOT NULL,
            segmentation_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'unread' CHECK (status IN
                ('unread', 'reading', 'proposed', 'adopted', 'approved', 'reopened')),
            scenario text NOT NULL DEFAULT 'base'
                CHECK (scenario IN ('base', 'principal_invaded')),
            read_run_id uuid NULL,
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no > 0),
            content_hash text NULL CHECK (content_hash {_SHA}),
            locked_at timestamptz NULL,
            reopen_reason_sealed bytea NULL
                CHECK (octet_length(reopen_reason_sealed) BETWEEN 1 AND 8192),
            superseded_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((status = 'approved') = (locked_at IS NOT NULL)),
            CHECK (status <> 'reopened' OR reopen_reason_sealed IS NOT NULL),
            {_RETURN_FK},
            FOREIGN KEY (tenant_id, instrument_id)
                REFERENCES governing_instruments (tenant_id, id),
            FOREIGN KEY (tenant_id, segmentation_id)
                REFERENCES instrument_segmentations (tenant_id, id),
            FOREIGN KEY (tenant_id, read_run_id) REFERENCES agent_runs (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX instrument_interpretations_current ON instrument_interpretations "
        "(tenant_id, work_item_id) WHERE superseded_at IS NULL"
    )
    op.execute(
        f"""
        CREATE TABLE instrument_determinations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            interpretation_id uuid NOT NULL,
            key text NOT NULL CHECK (key IN {_KEYS}),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (interpretation_id, key),
            FOREIGN KEY (tenant_id, interpretation_id)
                REFERENCES instrument_interpretations (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE instrument_determination_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            determination_id uuid NOT NULL,
            key text NOT NULL CHECK (key IN {_KEYS}),
            seq integer NOT NULL CHECK (seq > 0),
            value_code text NOT NULL CHECK (length(value_code) BETWEEN 1 AND 60),
            value_text_sealed bytea NOT NULL CHECK (octet_length(value_text_sealed) <= 2048),
            rationale_ref text NULL CHECK (length(rationale_ref) <= 120),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            {_SET_BY},
            suggestion_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (determination_id, seq),
            CHECK (key NOT IN {_GOVERNED} OR cardinality(citation_ids) >= 1),
            CHECK (NOT (set_by_kind = 'human' AND seq > 1) OR reason_sealed IS NOT NULL),
            CHECK (set_by_kind <> 'agent' OR suggestion_id IS NOT NULL),
            FOREIGN KEY (tenant_id, determination_id)
                REFERENCES instrument_determinations (tenant_id, id),
            FOREIGN KEY (tenant_id, suggestion_id) REFERENCES suggestions (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE fai_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_RETURN_COLS},
            kind text NOT NULL CHECK (kind IN ('interest', 'ordinary_dividends',
                'qualified_dividends', 'tax_exempt_interest', 'capital_gain', 'rents',
                'other_income')),
            parent_line_id uuid NULL,
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 200),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((kind = 'qualified_dividends') = (parent_line_id IS NOT NULL)),
            {_RETURN_FK},
            FOREIGN KEY (tenant_id, parent_line_id) REFERENCES fai_lines (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE fai_line_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            line_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq > 0),
            amount {_MONEY} NOT NULL,
            citation_ids uuid[] NOT NULL CHECK (cardinality(citation_ids) >= 1),
            {_SET_BY},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (line_id, seq),
            CHECK (set_by_kind = 'human'),
            CHECK (seq = 1 OR reason_sealed IS NOT NULL),
            FOREIGN KEY (tenant_id, line_id) REFERENCES fai_lines (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE trust_expenses (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_RETURN_COLS},
            kind text NOT NULL CHECK (kind IN ('trustee_fee', 'legal', 'accounting',
                'tax_preparation', 'other')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            {_RETURN_FK},
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE trust_expense_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            expense_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq > 0),
            charged_to text NOT NULL CHECK (charged_to IN ('income', 'principal')),
            amount {_MONEY} NOT NULL CHECK (amount >= 0),
            deductible boolean NOT NULL,
            clause_id uuid NULL,
            citation_ids uuid[] NOT NULL CHECK (cardinality(citation_ids) >= 1),
            {_SET_BY},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (expense_id, seq),
            CHECK (set_by_kind = 'human'),
            CHECK (seq = 1 OR reason_sealed IS NOT NULL),
            FOREIGN KEY (tenant_id, expense_id) REFERENCES trust_expenses (tenant_id, id),
            FOREIGN KEY (tenant_id, clause_id) REFERENCES instrument_clauses (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE trust_distributions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_RETURN_COLS},
            beneficiary_contact_id uuid NOT NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            {_RETURN_FK},
            FOREIGN KEY (tenant_id, beneficiary_contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE trust_distribution_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            distribution_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq > 0),
            paid_on date NOT NULL,
            amount {_MONEY} NOT NULL CHECK (amount > 0),
            form text NOT NULL DEFAULT 'cash' CHECK (form IN ('cash', 'in_kind')),
            source text NOT NULL DEFAULT 'income' CHECK (source IN ('income', 'principal')),
            clause_id uuid NULL,
            sixty_five_day_election_id uuid NULL,
            {_SET_BY},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (distribution_id, seq),
            CHECK (set_by_kind = 'human'),
            CHECK (seq = 1 OR reason_sealed IS NOT NULL),
            CHECK (source <> 'principal' OR clause_id IS NOT NULL),
            FOREIGN KEY (tenant_id, distribution_id)
                REFERENCES trust_distributions (tenant_id, id),
            FOREIGN KEY (tenant_id, clause_id) REFERENCES instrument_clauses (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE fai_dni_computations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_RETURN_COLS},
            version_no integer NOT NULL CHECK (version_no > 0),
            interpretation_hash text NOT NULL CHECK (interpretation_hash {_SHA}),
            inputs_hash text NOT NULL CHECK (inputs_hash {_SHA}),
            engine_name text NOT NULL CHECK (engine_name = 'fiduciary'),
            engine_version text NOT NULL CHECK (engine_version ~ '^[0-9]+\\.[0-9]+\\.[0-9]+$'),
            parameter_set text NOT NULL CHECK (parameter_set ~ '^ty[0-9]{{4}}(@[0-9]+)?$'),
            income_distribution_deduction {_MONEY} NOT NULL
                CHECK (income_distribution_deduction >= 0),
            outputs jsonb NOT NULL CHECK (jsonb_typeof(outputs) = 'object'),
            prior_computation_id uuid NULL,
            computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id, version_no),
            {_RETURN_FK},
            FOREIGN KEY (tenant_id, prior_computation_id)
                REFERENCES fai_dni_computations (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE beneficiary_allocations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            computation_id uuid NOT NULL,
            beneficiary_contact_id uuid NOT NULL,
            distributions {_MONEY} NOT NULL CHECK (distributions >= 0),
            share numeric(9,6) NOT NULL CHECK (share BETWEEN 0 AND 1),
            dni_allocated {_MONEY} NOT NULL CHECK (dni_allocated >= 0),
            box_1 {_MONEY} NOT NULL,
            box_2a {_MONEY} NOT NULL,
            box_2b {_MONEY} NOT NULL,
            box_other jsonb NOT NULL DEFAULT '{{}}' CHECK (jsonb_typeof(box_other) = 'object'),
            UNIQUE (tenant_id, id),
            UNIQUE (computation_id, beneficiary_contact_id),
            CHECK (box_2b <= box_2a),
            FOREIGN KEY (tenant_id, computation_id)
                REFERENCES fai_dni_computations (tenant_id, id),
            FOREIGN KEY (tenant_id, beneficiary_contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE sixty_five_day_elections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            tax_year integer NOT NULL CHECK (tax_year BETWEEN 2000 AND 2100),
            seq integer NOT NULL CHECK (seq > 0),
            status text NOT NULL CHECK (status IN ('not_made', 'elected')),
            amount {_MONEY} NULL,
            paid_on date NULL,
            window_end date NOT NULL,
            decision_owner_contact_id uuid NOT NULL,
            recorded_by_user_id uuid NOT NULL,
            recorded_on_return_id uuid NULL,
            evidence_version_id uuid NULL,
            actor_kind text NOT NULL DEFAULT 'human' CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (client_entity_id, tax_year, seq),
            CHECK (status <> 'elected' OR (amount > 0 AND paid_on IS NOT NULL
                AND paid_on <= window_end)),
            CHECK (status <> 'not_made' OR (amount IS NULL AND paid_on IS NULL)),
            CHECK (window_end > make_date(tax_year, 12, 31)),
            FOREIGN KEY (tenant_id, client_entity_id)
                REFERENCES trust_profiles (tenant_id, client_entity_id),
            FOREIGN KEY (tenant_id, decision_owner_contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, recorded_by_user_id)
                REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )


def _grants() -> None:
    _lock_down(
        "trust_profiles",
        ("client_entity_id", "tenant_id", "fiduciary_kind", "agreement_date", "revocable",
         "irrevocable_since", "settlor_name_sealed", "settlor_died_year", "remainder_sealed",
         "residency_state", "residency_basis", "state_form", "created_by"),
        ("agreement_date", "revocable", "irrevocable_since", "settlor_name_sealed",
         "settlor_died_year", "remainder_sealed", "residency_state", "residency_basis",
         "state_form", "row_version"),
    )  # fmt: skip
    _lock_down(
        "governing_instruments",
        ("tenant_id", "client_entity_id", "evidence_version_id", "supersedes_instrument_id",
         "attached_by"),
    )  # fmt: skip
    _lock_down(
        "instrument_segmentations",
        ("tenant_id", "instrument_id", "segmentation_version", "text_source", "status",
         "confidence", "clause_count", "layer_sha256"),
    )  # fmt: skip
    _lock_down(
        "instrument_clauses",
        ("tenant_id", "segmentation_id", "label", "heading", "ordinal", "parent_clause_id",
         "page_from", "page_to", "regions", "text_sha256", "marked_by"),
    )  # fmt: skip
    _lock_down(
        "instrument_interpretations",
        ("tenant_id", "engagement_id", "work_item_id", "instrument_id", "segmentation_id"),
        ("status", "scenario", "read_run_id", "version_no", "content_hash", "locked_at",
         "reopen_reason_sealed", "superseded_at", "row_version"),
    )  # fmt: skip
    _lock_down("instrument_determinations", ("tenant_id", "interpretation_id", "key"))
    _lock_down(
        "instrument_determination_versions",
        ("tenant_id", "determination_id", "key", "seq", "value_code", "value_text_sealed",
         "rationale_ref", "citation_ids", "set_by_kind", "set_by_id", "reason_sealed",
         "suggestion_id"),
    )  # fmt: skip
    _lock_down(
        "fai_lines",
        ("tenant_id", "engagement_id", "work_item_id", "kind", "parent_line_id", "description",
         "created_by"),
    )  # fmt: skip
    _lock_down(
        "fai_line_versions",
        ("tenant_id", "line_id", "seq", "amount", "citation_ids", "set_by_kind", "set_by_id",
         "reason_sealed"),
    )  # fmt: skip
    _lock_down(
        "trust_expenses", ("tenant_id", "engagement_id", "work_item_id", "kind", "created_by")
    )
    _lock_down(
        "trust_expense_versions",
        ("tenant_id", "expense_id", "seq", "charged_to", "amount", "deductible", "clause_id",
         "citation_ids", "set_by_kind", "set_by_id", "reason_sealed"),
    )  # fmt: skip
    _lock_down(
        "trust_distributions",
        ("tenant_id", "engagement_id", "work_item_id", "beneficiary_contact_id", "created_by"),
    )
    _lock_down(
        "trust_distribution_versions",
        ("tenant_id", "distribution_id", "seq", "paid_on", "amount", "form", "source",
         "clause_id", "sixty_five_day_election_id", "set_by_kind", "set_by_id",
         "reason_sealed"),
    )  # fmt: skip
    _lock_down(
        "fai_dni_computations",
        ("tenant_id", "engagement_id", "work_item_id", "version_no", "interpretation_hash",
         "inputs_hash", "engine_name", "engine_version", "parameter_set",
         "income_distribution_deduction", "outputs", "prior_computation_id", "content_hash"),
    )  # fmt: skip
    _lock_down(
        "beneficiary_allocations",
        ("tenant_id", "computation_id", "beneficiary_contact_id", "distributions", "share",
         "dni_allocated", "box_1", "box_2a", "box_2b", "box_other"),
    )  # fmt: skip
    _lock_down(
        "sixty_five_day_elections",
        ("tenant_id", "client_entity_id", "tax_year", "seq", "status", "amount", "paid_on",
         "window_end", "decision_owner_contact_id", "recorded_by_user_id",
         "recorded_on_return_id", "evidence_version_id", "actor_kind"),
    )  # fmt: skip


def _triggers() -> None:
    # An interpretation's status moves forward; the only way back is approved → reopened →
    # proposed | adopted, and a run that stops before proposing returns reading → unread.
    op.execute(
        """
        CREATE FUNCTION instrument_interpretation_forward() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE
            v_old integer := CASE OLD.status WHEN 'unread' THEN 0 WHEN 'reading' THEN 1
                WHEN 'proposed' THEN 2 WHEN 'adopted' THEN 3 WHEN 'approved' THEN 4 ELSE 5 END;
            v_new integer := CASE NEW.status WHEN 'unread' THEN 0 WHEN 'reading' THEN 1
                WHEN 'proposed' THEN 2 WHEN 'adopted' THEN 3 WHEN 'approved' THEN 4 ELSE 5 END;
        BEGIN
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;
            IF OLD.status = 'approved' AND NEW.status <> 'reopened' THEN
                RAISE EXCEPTION 'interpretation_locked' USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status = 'reopened' AND NEW.status NOT IN ('proposed', 'adopted') THEN
                RAISE EXCEPTION 'instrument interpretation % may only move to proposed or adopted',
                    OLD.id USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status NOT IN ('approved', 'reopened')
               AND NOT (OLD.status = 'reading' AND NEW.status = 'unread')
               AND v_new < v_old THEN
                RAISE EXCEPTION 'instrument interpretation status moves forward only'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER instrument_interpretation_forward BEFORE UPDATE ON "
        "instrument_interpretations FOR EACH ROW EXECUTE FUNCTION "
        "instrument_interpretation_forward()"
    )
    # AC-4.2: no new determination version while the interpretation is approved (locked).
    op.execute(
        """
        CREATE FUNCTION instrument_determination_unlocked() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            IF (SELECT i.status FROM public.instrument_interpretations i
                  JOIN public.instrument_determinations d ON d.interpretation_id = i.id
                 WHERE d.id = NEW.determination_id) = 'approved' THEN
                RAISE EXCEPTION 'interpretation_locked' USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.key IS DISTINCT FROM (SELECT d.key FROM public.instrument_determinations d
                                          WHERE d.id = NEW.determination_id) THEN
                RAISE EXCEPTION 'determination version key differs from its determination'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER instrument_determination_unlocked BEFORE INSERT ON "
        "instrument_determination_versions FOR EACH ROW EXECUTE FUNCTION "
        "instrument_determination_unlocked()"
    )
    # Σ DNI allocated = the computation's income distribution deduction, checked at commit.
    op.execute(
        """
        CREATE FUNCTION beneficiary_allocations_tie() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        DECLARE
            v_idd numeric;
            v_sum numeric;
        BEGIN
            SELECT c.income_distribution_deduction INTO v_idd
              FROM public.fai_dni_computations c WHERE c.id = NEW.computation_id;
            SELECT coalesce(sum(a.dni_allocated), 0) INTO v_sum
              FROM public.beneficiary_allocations a WHERE a.computation_id = NEW.computation_id;
            IF v_sum <> v_idd THEN
                RAISE EXCEPTION 'beneficiary allocations do not tie to the deduction'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER beneficiary_allocations_tie AFTER INSERT ON "
        "beneficiary_allocations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION "
        "beneficiary_allocations_tie()"
    )


def upgrade() -> None:
    _tables()
    _grants()
    _triggers()


def downgrade() -> None:
    op.execute("DROP TRIGGER beneficiary_allocations_tie ON beneficiary_allocations")
    op.execute("DROP FUNCTION beneficiary_allocations_tie()")
    op.execute(
        "DROP TRIGGER instrument_determination_unlocked ON instrument_determination_versions"
    )
    op.execute("DROP FUNCTION instrument_determination_unlocked()")
    op.execute("DROP TRIGGER instrument_interpretation_forward ON instrument_interpretations")
    op.execute("DROP FUNCTION instrument_interpretation_forward()")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
