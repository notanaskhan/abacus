"""C-02-T33 (TASK-8905; ADR-167 / P-12; red): vendor TIN handling.

Row acceptance: "No TIN plaintext appears outside the sealed store, every reveal writes a
pii_reveals row naming the person, and an offshore user's reveal is refused." Here: the reveal is
P-03's `reveal_field` (the `pii_reveals` row with the person and `field_ref vendor:<id>:tin`), and
a refusal that is not MFA becomes `tin_reveal_refused`; the W-9 write seals the digits and sends
only the last four onward (no digit reaches an audit `Ref`, a log line or the response); TIN
Matching and backup-withholding rules; the classification is pure code.
"""

from __future__ import annotations

import ast
import re
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr

from abacus.modules.closes import vendor_tins
from abacus.modules.closes.compute import information_returns as irc
from abacus.modules.closes.delivery_contract import (
    DeliveryBackupWithholdingIn,
    DeliveryTinMatchIn,
    DeliveryVendorRowOut,
    DeliveryW9RecordIn,
)
from abacus.modules.closes.delivery_errors import TinRevealRefused
from abacus.modules.identity.api import Forbidden

SRC = Path(vendor_tins.__file__)
TIN = "981234471"


def _vendor(**over: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
    base = vendor_tins._Vendor(  # pyright: ignore[reportPrivateUsage]
        id=uuid4(),
        client_entity_id=uuid4(),
        display_name="Hartwell & Lowe LLP",
        entity_type="partnership",
        is_attorney=True,
        exempt_reason=None,
        tin_last4="4471",
        tin_kind="ein",
        w9_status="on_file",
        w9_signed_on=date(2026, 2, 3),
        backup_withholding="none",
        version=3,
        engagement=SimpleNamespace(id=uuid4()),  # pyright: ignore[reportArgumentType]
    )
    return replace(base, **over)


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        tenant=SimpleNamespace(tenant_id=uuid4()), tenant_id=uuid4(), user_id=uuid4()
    )


# --- the classification (code computes, ADR-050) ----------------------------------------------


def _pay(method: str, amount: str) -> irc.Payment:
    return irc.Payment(method, Decimal(amount), 1)


NEC_600 = irc.Threshold(Decimal(600), None)


def test_card_payments_are_the_processors_to_report() -> None:
    found = irc.classify(
        irc.VendorFacts("individual", False, None), [_pay("card", "900")], NEC_600
    )
    assert (found.reportability, found.amount) == ("paid_by_card", Decimal("0.00"))


def test_a_corporation_is_exempt_unless_it_is_an_attorney() -> None:
    corp = irc.classify(
        irc.VendorFacts("c_corporation", False, None), [_pay("ach", "9000")], NEC_600
    )
    assert corp.reportability == "exempt_corporation"
    lawyer = irc.classify(
        irc.VendorFacts("s_corporation", True, None), [_pay("ach", "9000")], NEC_600
    )
    assert (lawyer.reportability, lawyer.form, lawyer.box) == ("reportable", "nec", "1")


def test_threshold_counts_only_non_processor_payments() -> None:
    payments = [_pay("check", "400.00"), _pay("card", "300.00")]
    below = irc.classify(irc.VendorFacts("individual", False, None), payments, NEC_600)
    assert (below.reportability, below.amount) == ("below_threshold", Decimal("400.00"))
    payments.append(_pay("ach", "200.00"))
    at = irc.classify(irc.VendorFacts("individual", False, None), payments, NEC_600)
    assert (at.reportability, at.amount) == ("reportable", Decimal("600.00"))


def test_a_recorded_exemption_exempts() -> None:
    found = irc.classify(
        irc.VendorFacts("individual", False, "tax_exempt_org"), [_pay("ach", "5000")], NEC_600
    )
    assert found.reportability == "exempt_corporation"


@pytest.mark.parametrize(
    ("current", "result", "after"),
    [
        ("on_file", "mismatch", "tin_mismatch"),
        ("on_file", "not_issued", "tin_mismatch"),
        ("tin_mismatch", "match", "on_file"),
        ("on_file", "match", "on_file"),
        ("requested", "match", "requested"),
    ],
)
def test_tin_matching_moves_the_w9_status(current: str, result: str, after: str) -> None:
    assert irc.w9_status_after_match(current, result) == after  # type: ignore[arg-type]


def test_backup_withholding_transitions() -> None:
    assert irc.backup_state_after("none", "b_notice_received") == "watch"
    assert irc.backup_state_after("watch", "started") == "started"
    assert irc.backup_state_after("started", "started") is None
    assert irc.backup_state_after("none", "stopped") is None
    assert irc.backup_state_after("started", "stopped") == "none"


# --- the reveal is P-03's, naming the person; offshore is refused -----------------------------


async def test_the_reveal_is_p03s_field_reveal_named_for_the_vendor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vendor = _vendor()
    seen: dict[str, object] = {}

    async def scoped(*_: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
        return vendor

    async def reveal_field(ctx: object, engagement_id: UUID, field_ref: str, kind: str, *_: object,
                           context_ref: str | None = None) -> object:  # fmt: skip
        seen.update(engagement=engagement_id, field=field_ref, kind=kind, context=context_ref)
        return SimpleNamespace(value="98-1234471")

    monkeypatch.setattr(vendor_tins, "_vendor", scoped)
    monkeypatch.setattr(vendor_tins, "reveal_field", reveal_field)
    kind, revealed = await vendor_tins.reveal_vendor_tin(_ctx(), vendor.id)  # type: ignore[arg-type]
    assert (kind, revealed.value) == ("ein", "98-1234471")
    assert seen == {
        "engagement": vendor.engagement.id,
        "field": f"vendor:{vendor.id}:tin",
        "kind": "ein",
        "context": "closes.information_returns",
    }
    # The field ref satisfies pii_reveals' CHECK (0652).
    assert re.fullmatch(r"[a-z][a-z_]{0,39}:[0-9a-f-]{36}:[a-z_]{1,20}", str(seen["field"]))


@pytest.mark.parametrize("layer", ["condition", "role", "relationship"])
async def test_an_offshore_or_roleless_reveal_is_refused(
    monkeypatch: pytest.MonkeyPatch, layer: str
) -> None:
    async def scoped(*_: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
        return _vendor()

    async def refused(*_: object, **__: object) -> object:
        raise Forbidden("pii.reveal", layer)  # type: ignore[arg-type]

    monkeypatch.setattr(vendor_tins, "_vendor", scoped)
    monkeypatch.setattr(vendor_tins, "reveal_field", refused)
    with pytest.raises(TinRevealRefused):
        await vendor_tins.reveal_vendor_tin(_ctx(), uuid4())  # type: ignore[arg-type]


async def test_a_stale_mfa_is_not_masked_as_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scoped(*_: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
        return _vendor()

    async def stale(*_: object, **__: object) -> object:
        raise Forbidden("pii.reveal", "attribute")

    monkeypatch.setattr(vendor_tins, "_vendor", scoped)
    monkeypatch.setattr(vendor_tins, "reveal_field", stale)
    with pytest.raises(Forbidden) as caught:
        await vendor_tins.reveal_vendor_tin(_ctx(), uuid4())  # type: ignore[arg-type]
    assert not isinstance(caught.value, TinRevealRefused)


async def test_no_tin_on_file_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scoped(*_: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
        return _vendor(tin_kind=None, tin_last4=None)

    monkeypatch.setattr(vendor_tins, "_vendor", scoped)
    from abacus.kernel.errors import NotFound

    with pytest.raises(NotFound):
        await vendor_tins.reveal_vendor_tin(_ctx(), uuid4())  # type: ignore[arg-type]


# --- the W-9's TIN never leaves the sealed store ----------------------------------------------


class _Tx:
    def __init__(self) -> None:
        self.params: list[dict[str, object]] = []
        self.records: list[tuple[str, object]] = []
        self.session = self

    async def scalar(self, _sql: object, params: dict[str, object]) -> object:
        self.params.append(params)
        return 4

    def begin_nested(self) -> _Tx:
        return self

    async def __aenter__(self) -> _Tx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def record(self, action: str, **kw: object) -> None:
        self.records.append((action, kw))


async def test_record_w9_seals_the_digits_and_audits_none_of_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vendor = _vendor(tin_kind=None, tin_last4=None, w9_status="requested")
    tx = _Tx()
    sealed_with: list[tuple[bytes, str]] = []

    async def scoped(*_: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
        return vendor

    async def on_engagement(*_: object) -> UUID:
        return vendor.engagement.id

    async def seal(_tenant: UUID, plain: bytes, aad: str) -> bytes:
        sealed_with.append((plain, aad))
        return b"envelope"

    async def read_back(*_: object) -> DeliveryVendorRowOut:
        return DeliveryVendorRowOut(
            vendor_id=vendor.id, display_name=vendor.display_name, entity_type="partnership",
            is_attorney=True, reportability="reportable", amount=Decimal("12500.00"),
            tin_last4="4471", w9_status="on_file", version=4,
        )  # fmt: skip

    monkeypatch.setattr(vendor_tins, "_vendor", scoped)
    monkeypatch.setattr(vendor_tins, "engagement_of_version", on_engagement)
    monkeypatch.setattr(vendor_tins, "seal", seal)
    monkeypatch.setattr(vendor_tins, "uow", lambda _tenant: tx)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(vendor_tins, "get_vendor", read_back)
    monkeypatch.setattr(vendor_tins, "fingerprint_tin", lambda *_: b"f" * 32)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    body = DeliveryW9RecordIn(
        tin=SecretStr("98-1234471"), tin_kind="ein", evidence_version_id=uuid4(),
        signed_on=date(2026, 2, 3), expected_version=3,
    )  # fmt: skip
    out = await vendor_tins.record_w9(_ctx(), vendor.id, body)  # type: ignore[arg-type]
    assert sealed_with == [(TIN.encode(), f"vendor_1099_tin:{vendor.id}")]
    written = tx.params[0]
    assert written["sealed"] == b"envelope" and written["last4"] == "4471"
    assert TIN not in repr(written)  # the row gets the envelope, never the digits
    assert TIN not in repr(tx.records) and "1234471" not in repr(tx.records)
    assert out.tin_last4 == "4471" and TIN not in out.model_dump_json()
    assert "981234471" not in repr(body) and "98-1234471" not in repr(body)


async def test_an_ssn_waits_for_the_consent_gate_on_a_real_firm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.organisations.api import TinKindNotAllowed

    async def real(*_: object) -> bool:
        return False

    vendor = _vendor()

    async def same(*_: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
        return vendor

    async def mine(*_: object) -> UUID:
        return vendor.engagement.id

    monkeypatch.setattr(vendor_tins, "_vendor", same)
    monkeypatch.setattr(vendor_tins, "engagement_of_version", mine)
    monkeypatch.setattr(vendor_tins, "consent_registered", lambda _p: False)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(vendor_tins, "is_synthetic_firm", real)
    body = DeliveryW9RecordIn(
        tin=SecretStr("123-45-6789"), tin_kind="ssn", evidence_version_id=uuid4(),
        signed_on=date(2026, 2, 3), expected_version=3,
    )  # fmt: skip
    with pytest.raises(TinKindNotAllowed):
        await vendor_tins.record_w9(_ctx(), vendor.id, body)  # type: ignore[arg-type]


async def test_evidence_off_the_close_engagement_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.kernel.errors import NotFound

    vendor = _vendor()

    async def elsewhere(*_: object) -> UUID:
        return uuid4()

    monkeypatch.setattr(vendor_tins, "engagement_of_version", elsewhere)
    with pytest.raises(NotFound):
        await vendor_tins._evidence_on(_ctx(), vendor, uuid4())  # type: ignore[arg-type]


# --- TIN Matching and backup withholding ------------------------------------------------------


async def test_tin_matching_needs_a_tin_on_file(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scoped(*_: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
        return _vendor(tin_kind=None, tin_last4=None)

    monkeypatch.setattr(vendor_tins, "_vendor", scoped)
    body = DeliveryTinMatchIn(
        checked_on=date(2026, 11, 2), result="match", evidence_version_id=uuid4()
    )
    with pytest.raises(vendor_tins.TinNotOnFile):
        await vendor_tins.record_tin_match(_ctx(), uuid4(), body)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("notice", "today", "signed", "reason"),
    [
        (None, date(2026, 11, 2), date(2026, 2, 3), "no_b_notice"),
        (date(2026, 10, 1), date(2026, 11, 2), date(2026, 2, 3), "within_30_business_days"),
        (date(2026, 8, 3), date(2026, 11, 2), date(2026, 9, 1), "tin_certified_since_notice"),
    ],
)
async def test_backup_withholding_waits_thirty_business_days(
    monkeypatch: pytest.MonkeyPatch, notice: date | None, today: date, signed: date, reason: str
) -> None:
    vendor = _vendor(backup_withholding="watch", w9_signed_on=signed)

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def scalar(self, *_: object) -> date | None:
            return notice

    async def now() -> date:
        return today

    async def days(start: date, end: date) -> int:
        return sum(
            1 for d in range((end - start).days) if (start.toordinal() + d + 1) % 7 not in (6, 0)
        )

    monkeypatch.setattr(vendor_tins, "tenant_session", lambda _t: _Session())  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(vendor_tins, "today", now)
    monkeypatch.setattr(vendor_tins, "business_days_between", days)
    with pytest.raises(vendor_tins.BackupWithholdingNotDue) as caught:
        await vendor_tins._withholding_due(_ctx(), vendor)  # type: ignore[arg-type]
    assert caught.value.facts["reason"] == reason


async def test_a_missing_tin_makes_withholding_due_now() -> None:
    vendor = _vendor(w9_status="missing", tin_kind=None, tin_last4=None)
    await vendor_tins._withholding_due(_ctx(), vendor)  # type: ignore[arg-type]


async def test_a_b_notice_needs_its_received_date(monkeypatch: pytest.MonkeyPatch) -> None:
    vendor = _vendor()

    async def scoped(*_: object) -> vendor_tins._Vendor:  # pyright: ignore[reportPrivateUsage]
        return vendor

    async def mine(*_: object) -> UUID:
        return vendor.engagement.id

    monkeypatch.setattr(vendor_tins, "_vendor", scoped)
    monkeypatch.setattr(vendor_tins, "engagement_of_version", mine)
    body = DeliveryBackupWithholdingIn(
        event="b_notice_received", reason="CP2100 received", evidence_version_id=uuid4()
    )
    with pytest.raises(vendor_tins.EvidenceRequired):
        await vendor_tins.record_backup_withholding(_ctx(), vendor.id, body)  # type: ignore[arg-type]


# --- static: nothing logs, emits or prints a TIN ----------------------------------------------


def test_the_module_never_logs_or_emits() -> None:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not names & {"_log", "get_logger", "print", "emit", "OutboxEvent"}


def test_the_routes_call_the_service() -> None:
    contract = (SRC.parent / "delivery_contract.py").read_text(encoding="utf-8")
    for call in ("get_vendor(", "record_w9(", "reveal_vendor_tin(", "record_tin_match(",
                 "record_backup_withholding("):  # fmt: skip
        assert f"vendor_tins.{call}" in contract, call
    assert '"/vendors/{vendor_id}/w9"' in contract
