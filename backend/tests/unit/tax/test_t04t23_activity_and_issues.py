"""T-04-T23 (TASK-6724; SPEC-649 AC-4.1, AC-4.7, AC-5.1, AC-5.6; INV-1, INV-5): TAX-06's
category paths and CSV cells, and TAX-07's titles, pure."""

from __future__ import annotations

import uuid

import pytest

from abacus.modules.audit_trail.engagement_activity import ActivityFilter
from abacus.modules.review.issues import IssueSource
from abacus.modules.tax.activity_kinds import ACTIVITY_KINDS, GROUP_OF, title
from abacus.modules.tax.return_issues import (
    _cell,  # pyright: ignore[reportPrivateUsage]  # the CSV cell rule under test
    category_for,
    dependency_ref,
)


def test_ac_titles_name_the_person_and_via_agent_and_never_an_agent_approval() -> None:
    assert title("document.approved", "human", "Samuel Ito", None) == (
        "Document approved by Samuel Ito"
    )
    assert title("field.value_recorded", "agent", "", "Kevin Osei") == (
        "Field changed by Kevin Osei via Agent"
    )
    assert (
        title("checkpoint.proposed", "agent", "", None) == "Checkpoint proposed by Accrued Agent"
    )
    assert title("tax_return.approved", "agent", "", "Kevin Osei") == "Return approved"
    assert title("issue.system_resolved", "system", "", None) == (
        "Issue resolved when the K-1 was released"
    )


def test_every_tax_kind_has_a_group_and_no_agent_self_action_is_a_decision() -> None:
    assert set(ACTIVITY_KINDS) <= set(GROUP_OF)
    assert set(GROUP_OF.values()) <= {"approvals", "client", "agent", "tax_engine", "issues"}
    for action, kind in ACTIVITY_KINDS.items():
        assert not (kind.agent_self and kind.mark == "ok"), action


def test_ac_category_paths_and_formula_cells() -> None:
    assert category_for("self_check", "box_18a_state") == "income/k1"
    assert category_for("k1_dependency", "draft_k1") == "approvals/k1"
    assert category_for("manual", "anything") == "manual"
    for lead in ("=SUM(A1)", "+1", "-1", "@x", "\tx"):
        assert _cell(lead).startswith("'")
    assert _cell("Draft K-1") == "Draft K-1"
    assert dependency_ref(uuid.UUID(int=1)).startswith("k1_dependency:")


def test_only_a_dependency_resolves_by_the_system_alone() -> None:
    IssueSource("k1_dependency", "approvals/k1", system_resolved_only=True)
    with pytest.raises(ValueError):
        IssueSource("self_check", "income/k1", system_resolved_only=True)


def test_ac_the_activity_filter_narrows_to_one_return() -> None:
    engagement, item = uuid.uuid4(), uuid.uuid4()
    plain = ActivityFilter(engagement)
    narrowed = ActivityFilter(engagement, work_item_id=item)
    assert plain.digest() != narrowed.digest()
    assert plain.fingerprint() != narrowed.fingerprint()


def test_the_audit_trail_catalogue_carries_every_tax_kind() -> None:
    """Nothing imports audit_trail, so its catalogue and links hold the tax kinds; this keeps the
    two in step."""
    from abacus.modules.audit_trail.activity_catalogue import CATALOGUE
    from abacus.modules.audit_trail.engagement_activity import ACTIVITY_LINKS

    for action, kind in ACTIVITY_KINDS.items():
        assert (CATALOGUE[action].category, CATALOGUE[action].mark) == (kind.category, kind.mark)
        assert ACTIVITY_LINKS[action].link_kind == kind.link_kind
