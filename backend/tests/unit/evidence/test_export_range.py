"""A-01-T22 (DEC-536): the export download's one-range parser, and the stream's geometry."""

from __future__ import annotations

import uuid

import pytest

from abacus.modules.evidence import export_download
from abacus.modules.evidence.export_download import ByteRange, RangeNotSatisfiable, parse_range


def test_no_header_is_the_whole_bundle() -> None:
    assert parse_range(None, 100) is None


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=0-9", ByteRange(0, 9)),
        ("bytes=10-", ByteRange(10, 99)),
        ("bytes=90-500", ByteRange(90, 99)),  # an end past the bundle is clamped
        ("bytes=-10", ByteRange(90, 99)),
        ("bytes=-1000", ByteRange(0, 99)),  # a suffix longer than the bundle is all of it
        (" bytes = 5 - 5 ", ByteRange(5, 5)),
        ("bytes=0-99", ByteRange(0, 99)),
    ],
)
def test_one_range_is_served(header: str, expected: ByteRange) -> None:
    assert parse_range(header, 100) == expected


@pytest.mark.parametrize(
    "header",
    [
        "bytes=0-1,5-9",  # several ranges
        "bytes=100-",  # a start at the end
        "bytes=150-160",
        "bytes=9-5",  # backwards
        "bytes=-0",  # an empty suffix
        "bytes=-",
        "bytes=",
        "bytes=a-b",
        "bites=0-1",
        "bytes=0-1;",
        "bytes=12345678901234567890-",  # 20 digits: never parsed
        "bytes=0x10-",
        "",
    ],
)
def test_anything_else_is_416(header: str) -> None:
    with pytest.raises(RangeNotSatisfiable) as refused:
        parse_range(header, 100)
    assert refused.value.size == 100


def test_an_empty_bundle_serves_no_range() -> None:
    with pytest.raises(RangeNotSatisfiable):
        parse_range("bytes=0-0", 0)


def test_the_file_name_is_ascii_from_the_id_only() -> None:
    export_id = uuid.uuid4()
    name = export_download.file_name(export_id)
    assert name == f"accrued-binder-{export_id}.zip" and name.isascii()


async def test_the_stream_reads_only_the_segments_its_range_needs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    size = 64 * 1024 * 1024 * 2 + 10  # three segments at the production size
    read: list[int] = []

    async def segment(
        _tenant: uuid.UUID, _export: uuid.UUID, n: int, *, kind: str = "engagement_export"
    ) -> bytes:
        assert kind == "engagement_export"  # an engagement bundle opens as its own kind only
        read.append(n)
        length = export_download.SEGMENT_BYTES if n < 2 else 10
        return bytes([n]) * length

    monkeypatch.setattr(export_download, "get_segment", segment)
    start = export_download.SEGMENT_BYTES * 2 + 3
    got = b"".join(
        [
            c
            async for c in export_download.stream_bytes(
                uuid.uuid4(), uuid.uuid4(), size, 3, start, 5
            )
        ]
    )
    assert got == bytes([2]) * 5 and read == [2]
