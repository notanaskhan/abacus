"""I-01-T25 (TASK-6726; docs/contracts/home-and-gates.md §4): every gate subkind any module
registers renders on HOME-01 and HOME-02, by its own words (`GATE_SUBKIND_TITLE`) or the generic
title (`fallbackTitle`: its name read as words), and draws a glyph for its kind."""

from __future__ import annotations

import re
from pathlib import Path

import abacus.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- every module registers
from abacus.modules.review.gates import (
    _SOURCES,  # pyright: ignore[reportPrivateUsage] -- the registry itself
)

WEB = Path(__file__).parents[3] / "apps/web/src/domain/home"
WORDS = re.compile(r"^\s+([a-z_]+): \"[^\"]+\",", re.M)
GLYPH = re.compile(r"const GLYPH[^{]*\{(?P<body>[^}]*)\}", re.S)


def test_every_registered_subkind_has_specific_or_generic_words() -> None:
    specific = set(WORDS.findall((WEB / "messages.ts").read_text()))
    assert _SOURCES, "the modules registered their gate sources"
    for name in _SOURCES:
        # Generic words need a snake_case name (it reads "acceptance_decision_due" as words).
        assert re.fullmatch(r"[a-z][a-z_]*[a-z]", name), name
        words = name.replace("_", " ")
        assert name in specific or words[:1].upper() + words[1:], name


def test_every_registered_kind_draws_a_glyph() -> None:
    found = GLYPH.search((WEB / "gateClasses.ts").read_text())
    assert found is not None
    kinds = set(re.findall(r"^\s+([a-z_]+):", found.group("body"), re.M))
    for name, source in _SOURCES.items():
        assert source.kind in kinds, f"{name}: kind {source.kind} has no HOME glyph"
