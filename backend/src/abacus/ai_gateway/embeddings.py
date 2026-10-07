"""Embeddings (SPEC-009 AC-5; TASK-024 D1). PROTECTED.

The only path to an embedding model. A call is bounded like any model call: its own budget on an
estimate, the budget hierarchy (SPEC-007), then admission on the embedding model (SPEC-003). Each
provider call writes a usage record (`prompt_id` `embed`, tier `small`), so metering and budgets
see embeddings as they see completions. Spans carry identifiers only, never the texts.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Protocol

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings

MAX_TEXTS: Final = 64
MAX_TEXT_CHARS: Final = 2_000
EMBED_PROMPT: Final = "embed"
_MILLION = Decimal(1_000_000)
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class EmbeddingResponse:
    vectors: tuple[tuple[float, ...], ...]
    input_tokens: int


class EmbeddingProvider(Protocol):
    async def embed(self, model: str, texts: tuple[str, ...]) -> EmbeddingResponse: ...


class FakeEmbedder:
    """Deterministic: hashed word features, L2-normalised. Texts sharing words score closer,
    so ranking is meaningful in tests. Synthetic environments only."""

    def __init__(self) -> None:
        if settings().environment not in SYNTHETIC_ENVIRONMENTS:
            raise RuntimeError("FakeEmbedder is for local runs and tests only")

    async def embed(self, model: str, texts: tuple[str, ...]) -> EmbeddingResponse:
        size = settings().embedding_dimensions
        vectors: list[tuple[float, ...]] = []
        for text in texts:
            vector = [0.0] * size
            for word in _WORD.findall(text.lower()):
                digest = hashlib.sha256(word.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % size
                vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append(tuple(v / norm for v in vector))
        tokens = sum(len(t) for t in texts) // 4
        return EmbeddingResponse(tuple(vectors), tokens)


_embedder: EmbeddingProvider | None = None


def configure_embedder(embedder: EmbeddingProvider | None) -> None:
    global _embedder
    _embedder = embedder


def embedder() -> EmbeddingProvider:
    """The configured provider; in synthetic environments the fake when none is configured."""
    global _embedder
    if _embedder is None:
        if settings().environment not in SYNTHETIC_ENVIRONMENTS:
            raise RuntimeError("no embedding provider configured")
        _embedder = FakeEmbedder()
    return _embedder


class EmbedTooLarge(ValueError):
    """More than 64 texts, an empty text, or a text over 2,000 characters."""


@dataclass(frozen=True)
class EmbedResult:
    vectors: tuple[tuple[float, ...], ...]
    model: str
    cost_usd: Decimal


def embed_cost(input_tokens: int) -> Decimal:
    price = settings().embedding_usd_per_million
    return (price * input_tokens / _MILLION).quantize(Decimal("0.000001"))
