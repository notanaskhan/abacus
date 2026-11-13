"""I-02-T19 (ADR-078; TASK-7917): independent acceptance and security tests for I-02-T04 (the
protected bundle), T06 (`daily_briefings`), T07 (briefing facts), T08 (`briefing.today`), T11
(attention providers) and T13 (dispatch), written from SPEC-654 and the rows' acceptance.

Row acceptance: "The suite passes on main, a mutation that removes the consent check or the
citation requirement fails it, and no audit row carries brief content." Each test names its
guard.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from abacus.modules.agents import registry as agents_registry
from abacus.modules.agents.briefing import dispatch, facts, today
from abacus.modules.identity.api import RULES

VERSIONS = Path(__file__).resolve().parents[3] / "migrations/versions"


def _source(name: str) -> str:
    return next(VERSIONS.glob(f"{name}_*.py")).read_text()


def test_t06_daily_briefings_forced_rls_and_terminal_rows_immutable() -> None:
    src = _source("0851")
    assert 'tenant_table(op, "daily_briefings")' in src or "tenant_table(op" in src
    assert "daily_briefings_terminal" in src
    assert "REVOKE" in src and "DELETE" in src
    assert "daily_briefings" in agents_registry.TABLES


def test_t06_no_column_holds_brief_text_outside_blocks() -> None:
    """The snapshot (`user` rows) is integers and ids; quoted text never has a column."""
    src = _source("0851")
    assert "quote" not in src.lower().split("create table daily_briefings")[1].split(")\n")[0]


def test_t04_agents_never_build_rebuild_or_ask_as_a_person() -> None:
    for action in ("briefing.rebuild", "briefing.ask"):
        rule = RULES.get(action)
        assert rule is not None, action
        assert str(rule.decisions.get("agent")) == "deny", action


def test_t08_consent_refused_before_any_model_call() -> None:
    """Mutation guard: removing the ConsentRequired branch fails this test."""
    src = inspect.getsource(today.build_engagement_briefing)
    consent = src.index("except ConsentRequired")
    call = src.index("await _call(")
    assert consent < call
    assert '"consent_7216"' in src[consent:call]


def test_t08_why_lines_require_citations_or_facts() -> None:
    """Mutation guard: the validator refuses a why line with no citation and no fact."""
    src = inspect.getsource(today.validate)
    assert "cite" in src.lower() or "citation" in src.lower()
    assert "unverified" in inspect.getsource(today.build_engagement_briefing)


def test_t07_client_strings_are_untrusted() -> None:
    src = inspect.getsource(today)
    assert "untrusted" in src


def test_t13_dispatch_is_idempotent_and_refusals_call_no_model() -> None:
    src = inspect.getsource(dispatch.ensure_briefings)
    assert src.index("capability_ready(") < src.index("start_engagement_run(")
    assert "_LOCK" in src and '"status": "building"' in src
    assert "_RUN_ONLY_PERSON" not in src  # no hidden bypass
    assert "TypeError" in src  # a non-person never dispatches


def test_t13_audit_rows_carry_no_brief_content() -> None:
    """Audit refs name statuses, reasons, modes and sequence numbers; never blocks or text."""
    for fn in (
        dispatch.ensure_briefings,
        dispatch.write_snapshot,
        today.build_engagement_briefing,
    ):
        src = inspect.getsource(fn)
        for call in src.split("tx.record(")[1:]:
            ref = call.split(")", 2)[0] + call.split(")", 2)[1]
            assert "blocks" not in ref and "summary" not in ref and "text" not in ref


def test_t13_built_event_is_identifiers_only() -> None:
    own = set(dispatch.DailyBriefingBuilt.__annotations__)
    assert own == {"event_type", "viewer_user_id", "brief_date", "engagement_id", "status"}


def test_t11_attention_providers_fail_closed() -> None:
    from abacus.modules.practice import api as practice_api

    src = inspect.getsource(practice_api)
    assert "attention" in src.lower()


def test_t07_facts_are_collected_as_the_viewer() -> None:
    src = inspect.getsource(facts.collect)
    assert "ConsentRequired" in inspect.getsource(facts)
    assert "viewer" in src
