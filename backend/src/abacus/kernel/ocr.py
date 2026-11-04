"""The OCR port (P-11-T23; P-11 §4.4; C4 v1.1; DEC-2251).

`OcrProvider` reads one page image and answers its words with boxes in **page points** and a
confidence for each, the same shape P-03's text layer has, so masking, citations, search and the
viewer work on scans. Two providers:

- `TextractOcr`: Amazon Textract through the us-east-2 interface endpoint (P-11-T22), one
  synchronous `DetectDocumentText` (or `AnalyzeDocument` for forms and tables) call per page's
  bytes, with exponential backoff on throttling and a response cache keyed by the page image's
  SHA-256, so the same page is never billed twice in a process.
- `FakeOcr`: replays recorded Textract JSON byte for byte (tests and synthetic firms).

Only `abacus.modules.evidence` calls this port (import-linter). It never logs page text, a TIN
or a word: its log lines carry counts and the image hash only. The gate (kill switch, firm flag,
provider terms, boundary basis, §7216) is `evidence.ocr_gate`'s, in that order, before any call.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, Literal, Protocol, cast

from abacus.kernel.logging import get_logger

JsonBlock = dict[str, Any]  # Any: boto3 and Textract JSON have no stubs

Api = Literal["detect_text", "analyze_forms", "analyze_tables"]
CACHE_PAGES: Final = 256
MAX_RETRIES: Final = 5
_log = get_logger(__name__)


@dataclass(frozen=True)
class OcrWord:
    text: str
    bbox: tuple[Decimal, Decimal, Decimal, Decimal]  # x0, y0, x1, y1 in page points
    confidence: Decimal  # 0 to 1


@dataclass(frozen=True)
class OcrPage:
    image_sha256: str
    words: tuple[OcrWord, ...]
    request_id: str | None

    @property
    def mean_confidence(self) -> Decimal:
        if not self.words:
            return Decimal(0)
        return (sum((w.confidence for w in self.words), Decimal(0)) / len(self.words)).quantize(
            Decimal("0.001")
        )

    def low_confidence_words(self, below: Decimal = Decimal("0.90")) -> int:
        return sum(1 for w in self.words if w.confidence < below)


class OcrProvider(Protocol):
    name: str

    async def read(
        self, image: bytes, *, width_pt: Decimal, height_pt: Decimal, api: Api
    ) -> OcrPage: ...


class OcrThrottled(Exception):
    """The provider kept throttling after the last retry."""


def _sha(image: bytes) -> str:
    return hashlib.sha256(image).hexdigest()


def normalise(
    blocks: Sequence[Mapping[str, Any]],  # Any: Textract blocks are untyped JSON
    *,
    width_pt: Decimal,
    height_pt: Decimal,
) -> tuple[OcrWord, ...]:
    """Textract's WORD blocks to words in page points (its boxes are page ratios)."""
    out: list[OcrWord] = []
    for block in blocks:
        if block.get("BlockType") != "WORD":
            continue
        box = block["Geometry"]["BoundingBox"]
        left, top = Decimal(str(box["Left"])), Decimal(str(box["Top"]))
        w, h = Decimal(str(box["Width"])), Decimal(str(box["Height"]))
        q = Decimal("0.01")
        out.append(
            OcrWord(
                str(block.get("Text", "")),
                (
                    (left * width_pt).quantize(q),
                    (top * height_pt).quantize(q),
                    ((left + w) * width_pt).quantize(q),
                    ((top + h) * height_pt).quantize(q),
                ),
                (Decimal(str(block.get("Confidence", 0))) / 100).quantize(Decimal("0.001")),
            )
        )
    return tuple(out)


class _Cache:
    def __init__(self, size: int = CACHE_PAGES) -> None:
        self._size = size
        self._pages: OrderedDict[tuple[str, str], OcrPage] = OrderedDict()

    def get(self, key: tuple[str, str]) -> OcrPage | None:
        found = self._pages.get(key)
        if found is not None:
            self._pages.move_to_end(key)
        return found

    def put(self, key: tuple[str, str], page: OcrPage) -> None:
        self._pages[key] = page
        self._pages.move_to_end(key)
        while len(self._pages) > self._size:
            self._pages.popitem(last=False)


class TextractOcr:
    """Textract, one synchronous call per page's bytes, through the VPC endpoint."""

    name = "textract"

    def __init__(self, client: Any | None = None, *, sleep: Any = asyncio.sleep) -> None:  # noqa: ANN401 -- the boto3 Textract client has no stubs in the allowlist
        self._client: Any = client  # Any: boto3 ships no stubs
        self._sleep = sleep
        self._cache = _Cache()

    def _textract(self) -> Any:  # noqa: ANN401 -- see above
        if self._client is None:
            from abacus.kernel.storage import textract_client

            self._client = textract_client()
        return self._client

    async def read(
        self, image: bytes, *, width_pt: Decimal, height_pt: Decimal, api: Api
    ) -> OcrPage:
        sha = _sha(image)
        cached = self._cache.get((sha, api))
        if cached is not None:
            return cached
        delay = 0.5
        response: JsonBlock = {}
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await asyncio.to_thread(self._call, image, api)
                break
            except Exception as exc:
                code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                if code not in ("ThrottlingException", "ProvisionedThroughputExceededException"):
                    raise
                if attempt == MAX_RETRIES:
                    _log.warning("ocr.throttled", image_sha256=sha, attempts=attempt + 1)
                    raise OcrThrottled from None
                await self._sleep(delay)
                delay = min(delay * 2, 8.0)
        page = OcrPage(
            sha,
            normalise(response.get("Blocks", []), width_pt=width_pt, height_pt=height_pt),
            response.get("ResponseMetadata", {}).get("RequestId"),
        )
        _log.info("ocr.read", image_sha256=sha, words=len(page.words), api=api)
        self._cache.put((sha, api), page)
        return page

    def _call(self, image: bytes, api: Api) -> JsonBlock:
        client = self._textract()
        if api == "detect_text":
            return dict(client.detect_document_text(Document={"Bytes": image}))
        features = ["FORMS"] if api == "analyze_forms" else ["TABLES"]
        return dict(client.analyze_document(Document={"Bytes": image}, FeatureTypes=features))


class FakeOcr:
    """Recorded Textract JSON per page-image SHA-256: replays byte-identical layers."""

    name = "fake"

    def __init__(self, recordings: Mapping[str, str]) -> None:
        self._recordings = dict(recordings)

    async def read(
        self, image: bytes, *, width_pt: Decimal, height_pt: Decimal, api: Api
    ) -> OcrPage:
        del api
        sha = _sha(image)
        raw = self._recordings.get(sha)
        blocks = cast(list[JsonBlock], json.loads(raw).get("Blocks", [])) if raw else []
        return OcrPage(sha, normalise(blocks, width_pt=width_pt, height_pt=height_pt), None)
