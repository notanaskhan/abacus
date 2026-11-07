"""A-05-T49 (TASK-6003; DEC-2603): the `ebp_audits` entitlement and the EBP CPA memo.

Acceptance (the task row): "the entitlement refuses a non-synthetic firm without the signed memo".
The record (`reference/review.yaml`) and the memo's Status line move together, the memo names the
golden case list it reviewed, and `entitlement` answers None for a real firm until the record is
signed, while a synthetic firm holds the module as granted.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import api as assurance_api
from abacus.modules.assurance.compute.ebp import review
from abacus.modules.platform import entitlements

REPO = Path(__file__).resolve().parents[4]
MEMO = REPO / "docs" / "quality" / "golden-reviews" / "ebp@1.md"
GOLDENS = REPO / "backend" / "tests" / "golden" / "ebp"
TENANT = TenantContext(uuid.uuid4(), "human", "u")


def _row(enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=enabled,
        seats=None,
        agent_minutes_allowance=None,
        valid_from=date(2000, 1, 1),
        valid_to=None,
    )


@pytest.fixture
def granted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The firm holds an enabled `ebp_audits` row today."""

    class _Result:
        def first(self) -> SimpleNamespace:
            return _row()

    class _Session:
        async def execute(self, *_: object, **__: object) -> _Result:
            return _Result()

    @asynccontextmanager
    async def session(_tenant: TenantContext) -> AsyncGenerator[_Session]:
        yield _Session()

    async def today(_tenant: TenantContext) -> date:
        return date(2027, 12, 10)

    monkeypatch.setattr(entitlements, "tenant_session", session)
    monkeypatch.setattr(entitlements.clock, "today", today)


def _synthetic(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    async def is_synthetic(_tenant: TenantContext) -> bool:
        return value

    monkeypatch.setattr(entitlements, "is_synthetic_firm", is_synthetic)


def test_ac_ebp_audits_is_a_reviewed_module_with_its_check_registered() -> None:
    assert assurance_api.__name__  # importing assurance's api registers the check
    assert "ebp_audits" in entitlements.MODULES
    assert {"ebp_audits"} == entitlements.REVIEWED_MODULES
    assert entitlements._reviews["ebp_audits"] is review.review_signed  # pyright: ignore[reportPrivateUsage] -- the registration under test


@pytest.mark.usefixtures("granted")
async def test_ac_a_real_firm_is_refused_without_the_signed_memo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _synthetic(monkeypatch, False)
    monkeypatch.setitem(entitlements._reviews, "ebp_audits", lambda: False)  # pyright: ignore[reportPrivateUsage] -- the record unsigned
    assert await entitlements.entitlement(TENANT, "ebp_audits") is None


@pytest.mark.usefixtures("granted")
async def test_ac_a_real_firm_holds_it_once_signed(monkeypatch: pytest.MonkeyPatch) -> None:
    _synthetic(monkeypatch, False)
    monkeypatch.setitem(entitlements._reviews, "ebp_audits", lambda: True)  # pyright: ignore[reportPrivateUsage] -- the record signed
    found = await entitlements.entitlement(TENANT, "ebp_audits")
    assert found is not None and found.module == "ebp_audits"


@pytest.mark.usefixtures("granted")
async def test_ac_a_synthetic_firm_holds_it_unsigned(monkeypatch: pytest.MonkeyPatch) -> None:
    _synthetic(monkeypatch, True)
    monkeypatch.setitem(entitlements._reviews, "ebp_audits", lambda: False)  # pyright: ignore[reportPrivateUsage] -- the record unsigned
    assert await entitlements.entitlement(TENANT, "ebp_audits") is not None


@pytest.mark.usefixtures("granted")
async def test_ac_no_registered_check_refuses_a_real_firm(monkeypatch: pytest.MonkeyPatch) -> None:
    _synthetic(monkeypatch, False)
    monkeypatch.delitem(entitlements._reviews, "ebp_audits")  # pyright: ignore[reportPrivateUsage] -- fail closed
    assert await entitlements.entitlement(TENANT, "ebp_audits") is None


@pytest.mark.usefixtures("granted")
async def test_other_modules_ignore_the_review(monkeypatch: pytest.MonkeyPatch) -> None:
    _synthetic(monkeypatch, False)
    assert await entitlements.entitlement(TENANT, "tax_returns") is not None


def test_ac_the_record_and_the_memo_move_together() -> None:
    record = yaml.safe_load(review.REVIEW.read_text(encoding="utf-8"))
    memo = MEMO.read_text(encoding="utf-8")
    status = next(line for line in memo.splitlines() if line.startswith("| Status |"))
    assert record["memo"] == "ebp@1"
    if record["signed"]:
        assert "**signed**" in status and str(record["vault_ref"]).startswith("V-")
        assert review.review_signed()
    else:
        assert "awaiting the CPA's signature" in status
        assert not review.review_signed()


def test_a_signed_record_needs_a_date_and_a_vault_reference(tmp_path: Path) -> None:
    review.review_signed.cache_clear()
    try:
        for body, signed in (
            ({"memo": "ebp@1", "signed": True, "signed_on": None, "vault_ref": "V-1"}, False),
            (
                {"memo": "ebp@1", "signed": True, "signed_on": "2027-11-30", "vault_ref": None},
                False,
            ),
            (
                {"memo": "ebp@1", "signed": True, "signed_on": "2027-11-30", "vault_ref": "x"},
                False,
            ),
            (
                {"memo": "ebp@1", "signed": True, "signed_on": "2027-11-30", "vault_ref": "V-9"},
                True,
            ),
        ):
            path = tmp_path / "review.yaml"
            path.write_text(yaml.safe_dump(body), encoding="utf-8")
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(review, "REVIEW", path)
                review.review_signed.cache_clear()
                assert review.review_signed() is signed
    finally:
        review.review_signed.cache_clear()


def test_the_cpa_review_names_this_case_list() -> None:
    digest = hashlib.sha256()
    for path in sorted(GOLDENS.glob("*.yaml")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    assert digest.hexdigest() in MEMO.read_text(encoding="utf-8")
