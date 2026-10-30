"""The sampler version registry (ADR-340 §3; A-03-T04; SPEC-580 AC-9).

A version identifier is opaque and never reused; once registered here its behaviour is frozen and
pinned by the corpus. A sample set version records the identifier it was drawn with, so a
re-performer always runs the same code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from abacus.modules.sampling.compute import v2_3


@dataclass(frozen=True)
class SamplerVersion:
    identifier: str
    methods: tuple[str, ...]
    select: Callable[..., v2_3.SampleDraw]
    frozen: bool


SAMPLER_VERSIONS: Final[Mapping[str, SamplerVersion]] = MappingProxyType(
    {v2_3.VERSION: SamplerVersion(v2_3.VERSION, v2_3.METHODS, v2_3.select, frozen=True)}
)
CURRENT: Final = v2_3.VERSION


def sampler(identifier: str) -> SamplerVersion:
    """The registered version, or KeyError (`unknown_sampler_version`)."""
    try:
        return SAMPLER_VERSIONS[identifier]
    except KeyError:
        raise KeyError("unknown_sampler_version") from None
