"""P-11-T23 (TASK-3271; DEC-2251): the OCR port and its gate.

Row acceptance: "Each refusal names its first failing condition and is audited without document
text, FakeOcr replays byte-identical layers, and no TIN or page text reaches logs, metrics or
error tracking."
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from abacus.kernel import ocr
from abacus.modules.evidence import ocr_gate

BLOCKS = {
    "Blocks": [
        {
            "BlockType": "WORD",
            "Text": "CP2000",
            "Confidence": 99.1,
            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.05, "Width": 0.2, "Height": 0.02}},
        },
        {"BlockType": "LINE", "Text": "ignored"},
    ]
}
IMAGE = b"page-1-image"
SHA = hashlib.sha256(IMAGE).hexdigest()
LETTER = {"width_pt": Decimal(612), "height_pt": Decimal(792)}


def test_words_are_normalised_to_page_points_with_confidence() -> None:
    (word,) = ocr.normalise(BLOCKS["Blocks"], **LETTER)
    assert word.bbox == (Decimal("61.20"), Decimal("39.60"), Decimal("183.60"), Decimal("55.44"))
    assert word.confidence == Decimal("0.991")


def test_fake_ocr_replays_the_same_layer_byte_for_byte() -> None:
    fake = ocr.FakeOcr({SHA: json.dumps(BLOCKS)})
    a = asyncio.run(fake.read(IMAGE, api="detect_text", **LETTER))
    b = asyncio.run(fake.read(IMAGE, api="detect_text", **LETTER))
    assert a == b
    assert a.image_sha256 == SHA


def test_textract_retries_throttling_then_caches_by_image_hash() -> None:
    class Throttle(Exception):
        response: ClassVar[dict[str, dict[str, str]]] = {"Error": {"Code": "ThrottlingException"}}

    calls: list[int] = []

    class Client:
        def detect_document_text(
            self, **_: object
        ) -> dict[str, Any]:  # Any: test doubles and JSON
            calls.append(1)
            if len(calls) < 3:
                raise Throttle
            return BLOCKS

    async def no_sleep(_: float) -> None:
        return None

    provider = ocr.TextractOcr(Client(), sleep=no_sleep)
    page = asyncio.run(provider.read(IMAGE, api="detect_text", **LETTER))
    again = asyncio.run(provider.read(IMAGE, api="detect_text", **LETTER))
    assert len(calls) == 3
    assert page == again


_OPT_OUT = SimpleNamespace(ai_services_opt_out="AWS Organizations policy", tri_basis=None)
_NO_OPT_OUT = SimpleNamespace(ai_services_opt_out=None, tri_basis=None)


@pytest.mark.parametrize(
    ("killed", "flag", "entry", "facts", "expected"),
    [
        (True, True, _OPT_OUT, (True, False, False), "kill_switch"),
        (False, False, _OPT_OUT, (True, False, False), "flag_off"),
        (False, True, None, (True, False, False), "terms_not_covering"),
        (False, True, _NO_OPT_OUT, (False, False, False), "boundary_basis"),
        (False, True, _OPT_OUT, (False, True, False), "consent_missing"),
        (False, True, _OPT_OUT, (False, True, True), None),
    ],
)
def test_the_gate_names_its_first_failing_condition(
    monkeypatch: pytest.MonkeyPatch,
    killed: bool,
    flag: bool,
    entry: object,
    facts: tuple[bool, bool, bool],
    expected: str | None,
) -> None:
    async def control(*_: object, **__: object) -> bool:
        return killed

    async def flagged(*_: object) -> bool:
        return flag

    async def on(*_: object) -> date:
        return date(2027, 11, 4)

    monkeypatch.setattr(ocr_gate, "control_active", control)
    monkeypatch.setattr(ocr_gate, "flag_enabled", flagged)
    monkeypatch.setattr(ocr_gate, "today", on)
    monkeypatch.setattr(ocr_gate, "covering", lambda *_: entry)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType] -- the patched callable is untyped
    tenant: Any = SimpleNamespace(tenant_id=None)  # Any: test doubles and JSON
    assert asyncio.run(ocr_gate.first_refusal(tenant, ocr_gate.GateFacts(*facts))) == expected


def test_the_port_logs_counts_and_hashes_only() -> None:
    source = inspect.getsource(ocr)
    logged = [line for line in source.splitlines() if "_log." in line and "(" in line]
    assert logged
    for line in logged:
        assert "text=" not in line
        assert "word=" not in line
