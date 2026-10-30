"""T-01-T20 (TASK-2318; T-01 §3.7; ADM-08; DEC-1364): the return-ID template renders TAX-09's
ids, locked cells stay on (stricter-only), "who may export" only narrows, a second status mirrored
onto one engine status is 409 `mapping_conflict`, and the format check answers in codes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext, Resource
from abacus.modules.integrations import engine_settings as svc


@pytest.mark.parametrize(
    ("year", "letter", "code", "version", "expected"),
    [
        (2025, "I", "FeldJ", 3, "2025I:FeldJ:V3"),
        (2025, "P", "Ridgeline", 2, "2025P:Ridgeline:V2"),
        (2025, "F", "Calloway", 1, "2025F:Calloway:V1"),
        (2025, "I", "FeldJ", None, "2025I:FeldJ"),
    ],
)
def test_ac_a_the_template_renders_the_engine_ids(
    year: int, letter: str, code: str, version: int | None, expected: str
) -> None:
    got = svc.engine_return_id(
        svc.TEMPLATE, tax_year=year, type_letter=letter, client_code=code, version=version
    )
    assert got == expected


@pytest.mark.parametrize("key", ["export_after_final_approval", "import_requires_approval"])
def test_ac_locked_rules_cannot_be_turned_off(key: str) -> None:
    cell = next(c for c in svc.CELLS if c.key == key)
    with pytest.raises(svc.SettingLocked):
        svc._check_cell(cell, "false")  # pyright: ignore[reportPrivateUsage] -- the cell rule itself
    assert svc._check_cell(cell, "true") == "true"  # pyright: ignore[reportPrivateUsage] -- the cell rule itself


def test_who_may_export_only_narrows() -> None:
    cell = next(c for c in svc.CELLS if c.key == "who_may_export")
    for value in svc.EXPORTERS:
        assert svc._check_cell(cell, value) == value  # pyright: ignore[reportPrivateUsage] -- the cell rule itself
    with pytest.raises(svc.SettingInvalid):
        svc._check_cell(cell, "everyone")  # pyright: ignore[reportPrivateUsage] -- the cell rule itself


def test_a_template_without_the_version_suffix_is_invalid() -> None:
    cell = next(c for c in svc.CELLS if c.key == "return_id_template")
    with pytest.raises(svc.SettingInvalid):
        svc._check_cell(cell, "{Tax year}{Type}:{Client code}")  # pyright: ignore[reportPrivateUsage] -- the cell rule itself


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        "firm_admin",
        datetime.now(UTC),
    )


@pytest.fixture
def allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def authorise(ctx: AuthContext, action: str, resource: Resource) -> None:
        return None

    monkeypatch.setattr(svc, "authorise", authorise)


async def test_ac_f_two_statuses_onto_one_engine_status_is_a_conflict(allowed: None) -> None:
    rows = {"in_review": "In Review", "action_required": "In Review"}
    with pytest.raises(svc.MappingConflict) as raised:
        await svc.save_mapping(_ctx(), svc.ENGINE_KEY, "workflow_status", rows, 1)
    assert raised.value.code == "mapping_conflict"


async def test_an_unknown_accrued_status_is_invalid(allowed: None) -> None:
    with pytest.raises(svc.SettingInvalid):
        await svc.save_mapping(_ctx(), svc.ENGINE_KEY, "workflow_status", {"done": "Done"}, 1)


async def test_ac_d_the_format_check_answers_in_codes(
    allowed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(svc, "_CHECKS", [])
    assert await svc.format_check(_ctx(), svc.ENGINE_KEY) == svc.FormatCheck(
        False, ("no_engine_file",)
    )

    async def broken(tenant: TenantContext) -> svc.FormatCheck:
        raise RuntimeError("the engine file said something hostile")

    monkeypatch.setattr(svc, "_CHECKS", [broken])
    assert (await svc.format_check(_ctx(), svc.ENGINE_KEY)).problems == ("check_failed",)

    async def passed(tenant: TenantContext) -> svc.FormatCheck:
        return svc.FormatCheck(True, (), 3)

    monkeypatch.setattr(svc, "_CHECKS", [passed])
    assert await svc.format_check(_ctx(), svc.ENGINE_KEY) == svc.FormatCheck(True, (), 3)
