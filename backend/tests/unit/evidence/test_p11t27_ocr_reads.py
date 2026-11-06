"""P-11-T27 (TASK-5121; P-11 F7, F8; SPEC C4 v1.1): the OCR reads.

Row acceptance: "TIN fields return only last4 tokens, a field match lights its bbox in SHL-08 with
its label, and retry from an agent or worker context is refused." Rows are faked at the session;
`P-11-T30` proves walls and clients end to end.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from abacus.modules.evidence import ocr_reads
from abacus.modules.identity.api import AuthContext, Forbidden


def _row(**over: object) -> dict[str, object]:
    return {
        "field_key": "w2.box1",
        "label": "Form W-2 · box 1",
        "value_type": "money",
        "value_text": "48600.00",
        "last4": None,
        "page_no": 1,
        "bbox": [10, 20, 30, 40],
        "confidence": Decimal("0.981"),
        "low_confidence": False,
        "extractor_kind": "form_map",
        "ocr_run_id": None,
        "form_type": "w2",
        "tax_year": 2025,
        "form_map_version": "1",
    } | over


class _Result:
    def __init__(self, rows: Sequence[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _Result:
        return self

    def all(self) -> Sequence[dict[str, object]]:
        return self._rows


class _Session:
    def __init__(self, rows: Sequence[dict[str, object]]) -> None:
        self._rows = rows

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, *_: object) -> _Result:
        return _Result(self._rows)


def _arrange(monkeypatch: pytest.MonkeyPatch, rows: Sequence[dict[str, object]]) -> AuthContext:
    version = SimpleNamespace(id=uuid4(), engagement_id=uuid4())

    async def visible(_ctx: object, _id: object) -> SimpleNamespace:
        return version

    monkeypatch.setattr(ocr_reads, "visible_version", visible)

    def session_of(_tenant: object) -> _Session:
        return _Session(rows)

    monkeypatch.setattr(ocr_reads, "tenant_session", session_of)
    return cast(AuthContext, SimpleNamespace(tenant=SimpleNamespace(actor_kind="human")))


async def test_a_tin_returns_only_its_mask(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _arrange(
        monkeypatch, [_row(field_key="w2.ssn", value_type="tin", value_text="x", last4="6081")]
    )
    found = await ocr_reads.extracted_fields(ctx, uuid4(), None, None)
    box = found.items[0]
    assert box.value_text is None
    assert (box.mask_token or "").endswith("6081")


async def test_an_unsupported_form_answers_no_items(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _arrange(monkeypatch, [])
    found = await ocr_reads.extracted_fields(ctx, uuid4(), None, None)
    assert found.items == ()
    assert found.form_type is None


async def test_a_match_lights_its_box_with_its_label(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _arrange(monkeypatch, [_row()])
    version_id = uuid4()
    regions = await ocr_reads.field_regions(
        ctx, version_id, [ocr_reads.field_match_id(version_id, "w2.box1"), "other"]
    )
    assert len(regions) == 1
    _, page, rect, label = regions[0]
    assert (page, rect, label) == (1, [10.0, 20.0, 30.0, 40.0], "Form W-2 · box 1")


@pytest.mark.parametrize(
    ("extractor", "ocr", "kind"),
    [("form_map", None, "text_layer_map"), ("form_map", uuid4(), "ocr_map")],
)
def test_the_extractor_reads_in_the_contracts_words(
    extractor: str, ocr: object, kind: str
) -> None:
    assert ocr_reads._kind(extractor, cast("UUID | None", ocr)) == kind  # pyright: ignore[reportPrivateUsage]  # the mapping itself


@pytest.mark.parametrize("actor_kind", ["agent", "system"])
async def test_retry_is_a_persons(actor_kind: str) -> None:
    ctx = cast(AuthContext, SimpleNamespace(tenant=SimpleNamespace(actor_kind=actor_kind)))
    with pytest.raises(Forbidden):
        await ocr_reads.retry_text(ctx, uuid4())
