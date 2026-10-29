"""G-01-T19 (DEC-903): the M9 checklist rows "roles mapped (P-10); walls configured; offshore group
consent-gated" are executable items of `make go-live-check`: a staff member without a role
template fails `identity.roles_mapped`; an active wall passes `identity.walls`, none leaves it
manual for the dossier; the offshore row reports the group and the consent gate."""

from __future__ import annotations

from dataclasses import replace

from abacus_tools.go_live import evaluate

from .test_q04t009_go_live import AT, GREEN, by_id, calendar


def test_a_staff_member_without_a_role_template_fails_roles_mapped() -> None:
    items = by_id(evaluate("shadow", replace(GREEN, members_without_level=1), AT, calendar()))
    assert items["identity.roles_mapped"].status == "fail"
    assert "1 staff without a role template" in items["identity.roles_mapped"].value
    green = by_id(evaluate("shadow", GREEN, AT, calendar()))
    assert green["identity.roles_mapped"].status == "pass"


def test_walls_pass_when_one_is_active_and_stay_manual_when_none_is() -> None:
    walled = by_id(evaluate("shadow", replace(GREEN, walls_active=2), AT, calendar()))
    assert (walled["identity.walls"].status, walled["identity.walls"].value) == (
        "pass",
        "2 active walls",
    )
    none = by_id(evaluate("shadow", GREEN, AT, calendar()))
    assert none["identity.walls"].status == "manual" and none["identity.walls"].dossier


def test_the_offshore_row_reports_the_group_and_the_consent_gate() -> None:
    items = by_id(
        evaluate(
            "shadow",
            replace(GREEN, offshore_members=3, offshore_consented_clients=5),
            AT,
            calendar(),
        )
    )
    row = items["identity.offshore_consent_gated"]
    assert row.status == "pass"
    assert row.value.startswith("3 offshore members") and "5 clients consented" in row.value
