"""T-08-T18 (TASK-8839; SPEC-710 AC-20; HOME-03; DEC-5841): filing-deadline readers in signatures
and organisations.

Row acceptance: "Granite Peak's letter (Sep 16), the Ferris consents (Sep 23) and the Pryor 8879-F
(Sep 28) arrive as deadline facts with owners and no document content."
"""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.platform.api import FilingDeadlineWindow
from abacus.modules.signatures import deadline_sources as sig

OWNER = uuid.uuid4()


def _env(purpose: str, due: date, status: str = "sent") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), purpose=purpose, client_id=uuid.uuid4(), engagement_id=None,
        work_item_id=None, due_on=due, status=status, sent_by=OWNER,
    )  # fmt: skip


class _S:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    async def __aenter__(self) -> _S:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, *_a: object) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self.rows)


def test_ac_letter_consents_and_8879f(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        _env("engagement_letter", date(2026, 9, 16)),
        _env("consent_7216", date(2026, 9, 23)),
        _env("form_8879_f", date(2026, 9, 28)),
    ]
    monkeypatch.setattr(sig, "tenant_session", lambda _t: _S(rows))
    facts = asyncio.run(
        sig.envelope_deadlines(
            TenantContext(uuid.uuid4(), "system", "t"),
            FilingDeadlineWindow(date(2026, 9, 1), date(2026, 9, 30)),
        )
    )
    assert [(f.filing_label, f.due_on.day) for f in facts] == [
        ("Engagement letter", 16), ("§7216 consent", 23), ("Form 8879-F", 28),
    ]  # fmt: skip
    assert all(f.owner_user_ids == (OWNER,) for f in facts)
    fields = {f.name for f in dataclasses.fields(facts[0])}
    assert not fields & {"title", "message", "content", "text", "amount"}


def test_both_kinds_registered() -> None:
    import abacus.modules.organisations.api  # noqa: F401 -- registration at import
    import abacus.modules.signatures.api  # noqa: F401
    from abacus.modules.platform.api import filing_deadline_source_kinds

    assert {"envelope", "consent"} <= set(filing_deadline_source_kinds())
