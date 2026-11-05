"""A-05 M7: EBP loans, participant accounts and expenses (A-05-T41; A-05 §4.2 M7; EBP-05, EBP-08,
EBP-09; DEC-2301; expand-only).

On the EBP audit's work item, tenant-scoped with forced RLS:
- `ebp_participant_loans` (the rollforward from the recordkeeper's loan report) and
  `ebp_loan_offsets` (a loan offset is a distribution on Schedule H line 2e(1), never a deemed
  distribution, so the reported line is pinned).
- `ebp_participant_balances` (by participant and status) and `ebp_sdba_holdings`: **no plaintext
  SSN column exists**; each is sealed like the census (0642), with its last four and an HMAC
  fingerprint.
- `ebp_plan_expenses` (each cited to its 408(b)(2) disclosure where one is on file),
  `ebp_erisa_budget_lines`, `ebp_compliance_tests` (limits read from the CPA-reviewed file by plan
  year, ADR P-62) and `ebp_qualification_facts`.

Revision ID: 0667
Revises: 0666
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0667"
down_revision = "0666"
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
_SHA = "~ '^[0-9a-f]{64}$'"
_STAMPS = """
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),"""
_EVIDENCE = """
            evidence_version_id uuid NOT NULL,
            citation_id uuid NULL,"""
_EVIDENCE_FK = """
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),"""
_SEALED_SSN = f"""
            -- No plaintext SSN: sealed, last four and an HMAC fingerprint, like the census (0642).
            ssn_sealed bytea NULL CHECK (octet_length(ssn_sealed) <= 4096),
            ssn_fp text NULL CHECK (ssn_fp {_SHA}),
            ssn_last4 text NULL CHECK (ssn_last4 ~ '^[0-9]{{4}}$'),"""
_SEALED_CHECK = """
            CHECK ((ssn_sealed IS NULL) = (ssn_fp IS NULL)
                AND (ssn_fp IS NULL) = (ssn_last4 IS NULL)),"""
_PARTICIPANT_KEY = "participant_key text NOT NULL CHECK (participant_key ~ '^[A-Za-z0-9-]{1,40}$')"
_TABLES = (
    "ebp_participant_loans",
    "ebp_loan_offsets",
    "ebp_participant_balances",
    "ebp_sdba_holdings",
    "ebp_plan_expenses",
    "ebp_erisa_budget_lines",
    "ebp_compliance_tests",
    "ebp_qualification_facts",
)
_SCOPED = ("tenant_id", "engagement_id", "work_item_id")
_EV = ("evidence_version_id", "citation_id")
_SEALED = ("ssn_sealed", "ssn_fp", "ssn_last4")
INSERTS: dict[str, tuple[str, ...]] = {
    "ebp_participant_loans": (
        *_SCOPED, *_EV, "participant_key", "loan_ref", "status", "originated_on", "term_months",
        "is_residence", "vested_balance", "beginning_balance", "new_loans", "repayments",
        "offsets", "ending_balance", "limit_amount", "limit_result", "engine_version",
        "inputs_hash",
    ),
    "ebp_loan_offsets": (
        *_SCOPED, *_EV, "loan_id", "offset_on", "amount", "form_1099r_code", "reported_line",
    ),
    "ebp_participant_balances": (
        *_SCOPED, *_EV, "participant_key", "name", *_SEALED, "status", "beginning_balance",
        "contributions", "earnings", "distributions", "fees", "transfers", "ending_balance",
    ),
    "ebp_sdba_holdings": (
        *_SCOPED, *_EV, "participant_key", *_SEALED, "security_type", "description",
        "market_value",
    ),
    "ebp_plan_expenses": (
        *_SCOPED, *_EV, "provider_id", "line_key", "description", "disclosure_citation_id",
        "invoiced", "credits", "paid_from_plan", "schedule_h_line", "result", "issue_id",
    ),
    "ebp_erisa_budget_lines": (
        *_SCOPED, *_EV, "line_key", "kind", "amount", "occurred_on",
    ),
    "ebp_compliance_tests": (
        *_SCOPED, "test_key", "plan_year", "limit_amount", "limit_ref", "result", "proposed_by_kind",
        "accepted_by", "accepted_at", "finding_ref", "engine_version", "inputs_hash",
    ),
    "ebp_qualification_facts": (
        *_SCOPED, "evidence_version_id", "citation_id", "fact_key", "value", "result",
        "proposed_by_kind", "accepted_by", "accepted_at",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "ebp_participant_loans": (
        "status", "vested_balance", "beginning_balance", "new_loans", "repayments", "offsets",
        "ending_balance", "limit_amount", "limit_result", "engine_version", "inputs_hash",
        "citation_id", "version", "updated_at",
    ),
    "ebp_loan_offsets": ("citation_id", "form_1099r_code", "version", "updated_at"),
    "ebp_participant_balances": (
        "status", "beginning_balance", "contributions", "earnings", "distributions", "fees",
        "transfers", "ending_balance", "citation_id", "version", "updated_at",
    ),
    "ebp_sdba_holdings": ("security_type", "market_value", "citation_id", "version", "updated_at"),
    "ebp_plan_expenses": (
        "disclosure_citation_id", "invoiced", "credits", "paid_from_plan", "schedule_h_line",
        "result", "issue_id", "citation_id", "version", "updated_at",
    ),
    "ebp_erisa_budget_lines": ("amount", "citation_id", "version", "updated_at"),
    "ebp_compliance_tests": (
        "limit_amount", "limit_ref", "result", "accepted_by", "accepted_at", "finding_ref",
        "engine_version", "inputs_hash", "version", "updated_at",
    ),
    "ebp_qualification_facts": (
        "value", "result", "accepted_by", "accepted_at", "citation_id", "version", "updated_at",
    ),
}  # fmt: skip


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE ebp_participant_loans (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}{_EVIDENCE}
            {_PARTICIPANT_KEY},
            loan_ref text NOT NULL CHECK (loan_ref ~ '^[A-Za-z0-9_.-]{{1,40}}$'),
            status text NOT NULL CHECK (status IN ('active', 'new', 'paid_off', 'offset')),
            originated_on date NULL,
            term_months integer NULL CHECK (term_months BETWEEN 1 AND 480),
            is_residence boolean NOT NULL DEFAULT false,
            vested_balance {_MONEY} NULL CHECK (vested_balance >= 0),
            beginning_balance {_MONEY} NOT NULL DEFAULT 0 CHECK (beginning_balance >= 0),
            new_loans {_MONEY} NOT NULL DEFAULT 0 CHECK (new_loans >= 0),
            repayments {_MONEY} NOT NULL DEFAULT 0 CHECK (repayments >= 0),
            offsets {_MONEY} NOT NULL DEFAULT 0 CHECK (offsets >= 0),
            ending_balance {_MONEY} NOT NULL CHECK (ending_balance >= 0),
            limit_amount {_MONEY} NULL CHECK (limit_amount >= 0),
            limit_result text NULL CHECK (limit_result IN ('within', 'exception')),
            engine_version text NULL CHECK (char_length(engine_version) <= 40),
            inputs_hash text NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, loan_ref),
            CHECK (limit_result IS NULL OR inputs_hash IS NOT NULL),{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_loan_offsets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}{_EVIDENCE}
            loan_id uuid NOT NULL,
            offset_on date NOT NULL,
            amount {_MONEY} NOT NULL CHECK (amount > 0),
            form_1099r_code text NULL CHECK (form_1099r_code ~ '^[0-9A-Z]{{1,2}}$'),
            -- An offset is a distribution on line 2e(1); line 2g stays 0 (A-05 F7).
            reported_line text NOT NULL DEFAULT '2e(1)' CHECK (reported_line = '2e(1)'),{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, loan_id, offset_on),
            FOREIGN KEY (tenant_id, loan_id)
                REFERENCES ebp_participant_loans (tenant_id, id),{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_participant_balances (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}{_EVIDENCE}
            {_PARTICIPANT_KEY},
            name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 200),{_SEALED_SSN}
            status text NOT NULL CHECK (status IN ('active', 'terminated')),
            beginning_balance {_MONEY} NOT NULL DEFAULT 0,
            contributions {_MONEY} NOT NULL DEFAULT 0,
            earnings {_MONEY} NOT NULL DEFAULT 0,
            distributions {_MONEY} NOT NULL DEFAULT 0,
            fees {_MONEY} NOT NULL DEFAULT 0,
            transfers {_MONEY} NOT NULL DEFAULT 0,
            ending_balance {_MONEY} NOT NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, evidence_version_id, participant_key),{_SEALED_CHECK}
{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_sdba_holdings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}{_EVIDENCE}
            {_PARTICIPANT_KEY},{_SEALED_SSN}
            security_type text NOT NULL CHECK (char_length(btrim(security_type)) BETWEEN 1 AND 80),
            description text NULL CHECK (char_length(description) <= 200),
            market_value {_MONEY} NOT NULL,{_STAMPS}
            UNIQUE (tenant_id, id),{_SEALED_CHECK}
{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_plan_expenses (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}{_EVIDENCE}
            provider_id uuid NULL,
            line_key text NOT NULL CHECK (line_key ~ '^[a-z0-9_.-]{{1,80}}$'),
            description text NOT NULL CHECK (char_length(btrim(description)) BETWEEN 1 AND 200),
            disclosure_citation_id uuid NULL,
            invoiced {_MONEY} NOT NULL DEFAULT 0,
            credits {_MONEY} NOT NULL DEFAULT 0 CHECK (credits >= 0),
            paid_from_plan {_MONEY} NOT NULL,
            schedule_h_line text NOT NULL
                CHECK (schedule_h_line IN ('2i(1)', '2i(2)', '2i(3)', '2i(4)')),
            result text NULL CHECK (result IN ('tie', 'exception')),
            issue_id uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, line_key),
            CHECK (result IS DISTINCT FROM 'exception' OR issue_id IS NOT NULL),
            FOREIGN KEY (tenant_id, provider_id)
                REFERENCES ebp_service_providers (tenant_id, id),{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_erisa_budget_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}{_EVIDENCE}
            line_key text NOT NULL CHECK (line_key ~ '^[a-z0-9_.-]{{1,80}}$'),
            kind text NOT NULL CHECK (kind IN ('beginning', 'revenue_share', 'applied')),
            amount {_MONEY} NOT NULL,
            occurred_on date NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, line_key),{_EVIDENCE_FK}{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_compliance_tests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            test_key text NOT NULL CHECK (test_key ~ '^[a-z0-9_.-]{{1,80}}$'),
            plan_year integer NOT NULL CHECK (plan_year BETWEEN 2000 AND 2100),
            limit_amount {_MONEY} NULL CHECK (limit_amount >= 0),
            limit_ref text NULL CHECK (char_length(limit_ref) <= 120),
            result text NOT NULL CHECK (result IN ('pass', 'exception', 'exempt')),
            proposed_by_kind text NOT NULL CHECK (proposed_by_kind IN ('code', 'agent', 'human')),
            accepted_by uuid NULL,
            accepted_at timestamptz NULL,
            finding_ref jsonb NULL CHECK (finding_ref IS NULL
                OR jsonb_typeof(finding_ref) = 'object'),
            engine_version text NULL CHECK (char_length(engine_version) <= 40),
            inputs_hash text NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, plan_year, test_key),
            -- An exemption is a proposal until a person accepts it (A-05 F8): the service reads
            -- `accepted_at`; nothing here makes an unaccepted `exempt` final.
            CHECK ((accepted_by IS NULL) = (accepted_at IS NULL)),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE ebp_qualification_facts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            evidence_version_id uuid NULL,
            citation_id uuid NULL,
            fact_key text NOT NULL CHECK (fact_key ~ '^[a-z0-9_.-]{{1,80}}$'),
            value text NULL CHECK (char_length(value) <= 500),
            result text NOT NULL CHECK (result IN ('consistent', 'exception', 'not_evaluated')),
            proposed_by_kind text NOT NULL CHECK (proposed_by_kind IN ('code', 'agent', 'human')),
            accepted_by uuid NULL,
            accepted_at timestamptz NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, fact_key),
            CHECK ((accepted_by IS NULL) = (accepted_at IS NULL)),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERTS[table])
        op.execute(f"GRANT UPDATE ({', '.join(UPDATES[table])}) ON {table} TO abacus_app")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
