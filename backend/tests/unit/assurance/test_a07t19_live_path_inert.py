"""A-07-T19 (TASK-6108; A-07 §4.10, §8.1): the live-path registrations are in place and inert.

Row acceptance: "With every A-07 flag off, AUD-02, ENG-02, SIG-01 and HOME-02 responses for the
canary tenant are identical before and after the merge." Each surface reads only what these
registrations answer, so the proof is that every one answers nothing while the flags are off: no
rail row (AUD-02), no index tag (AUD-01/ENG-02), no envelope can be drafted or sent from the two
sources (SIG-01), no decision card can be raised and no notification kind fires (HOME-02).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- runs the registrations
from abacus.kernel.db import TenantContext
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance import a07_registrations as a07
from abacus.modules.assurance.sections import registered_index_tags, registered_sections
from abacus.modules.identity.api import AuthContext
from abacus.modules.notifications.kinds import kind_of
from abacus.modules.reporting import api as c11
from abacus.modules.signatures.api import envelope_source

pytestmark = pytest.mark.asyncio
TENANT = TenantContext(uuid4(), "system", "test")
CTX = cast(AuthContext, SimpleNamespace(tenant=TENANT))


@pytest.fixture(autouse=True)
def _flags_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """A-07-T33 (DEC-3106): every firm's A-07 flags at their default, off."""

    async def off(_tenant: TenantContext, _flag: object) -> bool:
        return False

    monkeypatch.setattr(a07, "flag_enabled", off)


def test_every_flag_is_off_by_default() -> None:
    assert {f.default for f in a07.FLAGS.values()} == {"false"}
    assert set(a07.FLAGS) == {
        "audits.completion",
        "audits.letters",
        "audits.report_release",
        "audits.archive",
    }


async def test_aud02_the_completion_and_reporting_rows_stay_out() -> None:
    keys = {key for key, *_ in a07.SECTIONS}
    rows = {s.key: s for s in registered_sections() if s.key in keys}
    assert set(rows) == keys
    for section in rows.values():
        assert await section.state_provider(TENANT, uuid4()) is None


async def test_aud01_no_tag_while_off() -> None:
    names = {t.name for t in registered_index_tags(metadata_only=True)}
    assert {"report_released", "archived"} <= names
    assert await a07.report_released_tags(TENANT, [uuid4()]) == {}
    assert await a07.archived_tags(TENANT, [uuid4()]) == {}


@pytest.mark.parametrize("kind", ["rep_letter", "governance_letter"])
async def test_sig01_no_envelope_can_be_drafted_or_sent_from_a_letter(kind: str) -> None:
    source = envelope_source(kind)
    # The governance letter drafts from a sent version (TASK-6543, DEC-3145), and only while the
    # letters are live for the firm: off, its draft is refused like its documents and signers.
    if source.draft is not None:
        with pytest.raises(a07.NotLive):
            await source.draft(CTX, uuid4())
    else:
        assert kind == "rep_letter"
    with pytest.raises(a07.NotLive):
        await source.documents(CTX, uuid4())
    with pytest.raises(a07.NotLive):
        await source.signers(CTX, uuid4())
    for check in source.checks:
        assert await check(CTX, uuid4()) == ["letters_not_live"]


def test_the_rep_letter_meets_g7_and_the_governance_letter_no_gate() -> None:
    assert envelope_source("rep_letter").gate == "G7"
    assert envelope_source("governance_letter").gate is None


async def test_envelope_completed_is_left_alone_while_off() -> None:
    event = OutboxEvent(uuid4(), uuid4(), "envelope.completed", {"source_kind": "rep_letter"})
    assert await a07.on_letter_envelope_completed(event) is None
    assert a07.SUBSCRIPTIONS["envelope.completed"] is a07.on_letter_envelope_completed


@pytest.mark.parametrize("kind", ["representation_letter", "governance_letter", "audit_report"])
async def test_the_c11_kinds_are_registered_and_render_nothing_final(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def off(*_a: object) -> bool:
        return False

    found = c11.document_kind(kind)
    assert found.retention_record_type == a07.RECORD_TYPE
    if kind != "audit_report":  # A-07-T30: the report's final is approved by the release grant
        assert await found.approval_provider(cast(c11.ApprovalRef, None)) is None
    # A-07-T33 (DEC-3106): the gate reads the firm's flags, so it is the tenant provider's.
    monkeypatch.setattr(a07, "live", off)
    provider = found.tenant_variables_provider
    assert provider is not None
    with pytest.raises(a07.NotLive):
        await provider(TENANT, cast(c11.OwnerRef, None), cast(c11.RenderScope, None))


@pytest.mark.parametrize("card", [a07._going_concern_card, a07._opinion_card])  # pyright: ignore[reportPrivateUsage]  # cards
async def test_home02_no_decision_card_can_be_raised(card: object) -> None:
    with pytest.raises(a07.NotLive):
        await card(TENANT, SimpleNamespace(work_item_id=uuid4()))  # type: ignore[operator]  # test double or SDK shape


async def test_no_report_version_and_no_seal_file_while_off() -> None:
    assert await a07.report_version_reviewables(TENANT, uuid4()) == []
    assert await a07.archive_seal_section(TENANT, cast(object, None)) == []  # type: ignore[arg-type]  # test double or SDK shape


@pytest.mark.parametrize(
    "code",
    [
        "eqr_requested",
        "rep_letter_signed",
        "rep_letter_date_mismatch",
        "governance_comm_overdue",
        "report_released",
        "archive_deadline_risk",
        "filing_due",
    ],
)
def test_the_c16_kinds_are_registered(code: str) -> None:
    assert kind_of(code) is not None
