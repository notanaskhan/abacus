"""F-03-T37 (DEC-137): a flag's lifetime is 90 days unless the entry names a founder override,
which allows up to 180. The override is on the record and names its decision."""

from __future__ import annotations

from datetime import date

import pytest

from abacus_tools.codegen import feature_flags


def _flag(expires: str, override: str | None = None) -> str:
    extra = f"\n    override: {override}" if override else ""
    return (
        "flags:\n  - name: probe.flag\n    description: probe\n    owner: ayushkbhatia\n"
        f"    created: 2026-10-23\n    expires: {expires}\n    kind: boolean\n"
        f"    default: false{extra}\n"
    )


def test_ninety_days_without_an_override() -> None:
    assert feature_flags.parse(_flag("2027-01-21"))[0].expires == date(2027, 1, 21)
    with pytest.raises(feature_flags.RegistryError, match="within 90 days"):
        feature_flags.parse(_flag("2027-01-22"))


def test_a_founder_override_allows_up_to_180_days() -> None:
    assert feature_flags.parse(_flag("2027-04-21", "DEC-137"))[0].expires == date(2027, 4, 21)
    with pytest.raises(feature_flags.RegistryError, match="within 180 days"):
        feature_flags.parse(_flag("2027-04-22", "DEC-137"))


def test_an_override_names_its_decision() -> None:
    with pytest.raises(feature_flags.RegistryError, match="names its decision"):
        feature_flags.parse(_flag("2027-04-21", "founder said so"))


def test_no_flag_expires_before_feb_1_or_is_owned_by_founder() -> None:
    """F-03-T37 acceptance, against the real registry."""
    entries = feature_flags.parse(feature_flags.source())
    assert [e.name for e in entries if e.expires < date(2027, 2, 1)] == []
    assert [e.name for e in entries if e.owner == "founder"] == []
