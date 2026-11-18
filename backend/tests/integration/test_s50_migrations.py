"""S50: 0960 to 0966 go down to 0954 and back up. 0960 (T-08-T05, season setup), 0961 (T-08-T06,
tax practice tools; T-05's planning_opportunities widened), 0962 (T-08-T07, filing deadlines),
0963 (Q-05-T05, practice quality), 0964 (Q-05-T06, records destruction; Q-02's tables extended),
0965 (C-02-T16, closes delivery) and 0966 (T-06-T14, other entity workpapers). Every new table
comes back with forced row-level security; insert-only tables refuse the app role UPDATE and
DELETE and carry their immutable triggers; the CHECKs and guard triggers the rules rely on exist;
the head is single (0954 → 0966)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0954"
NEW_TABLES = (
    "seasons", "season_manifests", "season_cohorts", "season_manifest_rows", "season_asks",
    "season_cohort_approvals", "season_cohort_withdrawals", "season_row_steps",
    "variance_explanation_versions", "variance_explanation_acceptances", "standards_runs",
    "standards_run_items", "standards_check_results", "standards_check_confirmations",
    "planning_screens", "planning_opportunity_events", "amendments",
    "amendment_explanation_versions", "return_supersessions", "aar_adjustments", "aar_elections",
    "filing_deadlines", "filing_deadline_alerts",
    "qm_settings", "qm_cycles", "qm_objectives", "qm_risks", "qm_responses", "qm_response_risks",
    "qm_register_imports", "qm_risk_assessment_reviews", "inspection_selection_rules",
    "inspections", "qm_findings", "qm_finding_evaluations", "qm_finding_links",
    "annual_evaluations", "agent_output_outcomes", "draft_final_field_facts",
    "destruction_batches", "destruction_batch_items", "destruction_item_exclusions",
    "destruction_approvals", "destruction_certificates",
    "close_deliverables", "close_deliverable_versions", "close_reopenings", "tax_handoffs",
    "aaa_lines", "shareholder_allocations", "tax_provisions", "rate_recon_items",
    "deferred_tax_items", "functional_expense_lines", "public_support_tests", "allocation_runs",
    "form_page_renders", "form_diagnostics",
)  # fmt: skip
INSERT_ONLY = (
    "season_cohort_approvals", "season_cohort_withdrawals", "season_row_steps",
    "variance_explanation_versions", "variance_explanation_acceptances",
    "standards_check_results", "standards_check_confirmations", "planning_screens",
    "planning_opportunity_events", "amendment_explanation_versions", "return_supersessions",
    "aar_elections", "qm_register_imports", "qm_risk_assessment_reviews",
    "inspection_selection_rules", "qm_finding_evaluations", "qm_finding_links",
    "destruction_batch_items", "destruction_item_exclusions", "destruction_approvals",
    "destruction_certificates", "close_deliverable_versions", "close_reopenings", "tax_handoffs",
)  # fmt: skip
CONSTRAINTS = {
    ("season_row_steps", "season_row_steps_error"): ("error_code IS NOT NULL",),
    ("functional_expense_lines", "functional_expense_lines_crossfoot"): ("fundraising",),
    ("tax_provisions", "tax_provisions_total"): ("deferred_tax", "total_provision"),
    ("inspections", "inspections_not_ep"): ("inspector_user_id <> ep_signer_user_id",),
    ("destruction_batches", "destruction_batches_phrase"): ("'DESTROY '",),
    ("planning_opportunities", "planning_opportunities_non_tax_consent"): (
        "consent_id IS NOT NULL",
    ),
    ("legal_holds", "legal_holds_reason_code_check"): ("state_controversy", "client_dispute"),
    ("evidence_versions", "evidence_versions_tombstone"): ("destruction_certificate_id",),
}
TRIGGERS = (
    ("season_manifest_rows", "season_rows_frozen"),
    ("season_cohort_withdrawals", "season_withdrawal_before_start"),
    ("tax_returns", "tax_return_accepted_frozen"),
    ("inspections", "inspection_objectivity"),
    ("destruction_batches", "destruction_batches_forward"),
    ("destruction_approvals", "destruction_approvals_two"),
    ("tax_handoffs", "tax_handoffs_supersede"),
    # 0968 (S50 follow-up, DEC-5641): the permitted write in the UPDATE trigger's WHEN.
    ("evidence_versions", "evidence_versions_no_update"),
    ("evidence_versions", "evidence_versions_no_delete"),
    ("tax_handoffs", "tax_handoffs_no_update"),
    ("filing_deadline_alerts", "filing_deadline_alerts_no_truncate"),
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_0960_to_0966_go_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in NEW_TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in NEW_TABLES:
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        assert forced, table


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_insert_only_tables_refuse_update_and_delete(private_db: sc.Database, table: str) -> None:
    for privilege in ("UPDATE", "DELETE"):
        held = _value(
            private_db, f"SELECT has_table_privilege('abacus_app', '{table}', '{privilege}')"
        )
        assert held is False, (table, privilege)
    trigger = _value(
        private_db,
        "SELECT count(*) FROM pg_trigger WHERE tgrelid = $1::regclass AND tgname = $2",
        table,
        f"{table}_immutable",
    )
    assert trigger == 1, table


@pytest.mark.parametrize(("key", "parts"), sorted(CONSTRAINTS.items()), ids=str)
def test_the_checks_hold_their_rules(
    private_db: sc.Database, key: tuple[str, str], parts: tuple[str, ...]
) -> None:
    table, name = key
    definition = str(
        _value(
            private_db,
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = $1::regclass AND conname = $2",
            table,
            name,
        )
    )
    for part in parts:
        assert part in definition, (name, part, definition)


@pytest.mark.parametrize(("table", "name"), TRIGGERS)
def test_the_guard_triggers_exist(private_db: sc.Database, table: str, name: str) -> None:
    found = _value(
        private_db,
        "SELECT count(*) FROM pg_trigger WHERE tgrelid = $1::regclass AND tgname = $2",
        table,
        name,
    )
    assert found == 1


def test_the_head_reaches_0966(private_db: sc.Database) -> None:
    scripts = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    )
    head = str(_value(private_db, "SELECT version_num FROM alembic_version"))
    # Single head; 0966 stays on the line as later migrations land (0968, S50 follow-up).
    assert head == scripts.get_current_head()
    assert {"0960", "0961", "0962", "0963", "0964", "0965", "0966"} <= {
        r.revision for r in scripts.walk_revisions("base", head)
    }


@pytest.mark.parametrize(
    ("table", "trigger", "allowed"),
    [
        ("evidence_versions", "evidence_versions_no_update", "destruction_tombstone"),
        ("tax_handoffs", "tax_handoffs_no_update", "app.tax_handoff_supersede"),
    ],
)
def test_0968_the_one_permitted_write_lives_in_the_when(
    private_db: sc.Database, table: str, trigger: str, allowed: str
) -> None:
    definition = str(
        _value(
            private_db,
            "SELECT pg_get_triggerdef(oid) FROM pg_trigger "
            "WHERE tgrelid = $1::regclass AND tgname = $2",
            table,
            trigger,
        )
    )
    assert "WHEN ((NOT (" in definition and allowed in definition, definition
    body = str(
        _value(
            private_db,
            "SELECT p.prosrc FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
            "WHERE t.tgrelid = $1::regclass AND t.tgname = $2",
            table,
            trigger,
        )
    )
    assert "RAISE EXCEPTION" in body and "RETURN" not in body.upper(), body
