"""SPEC-021 AC-2 (TASK-037): download names are ASCII-safe and never carry a path or quote."""

from __future__ import annotations

from datetime import date

import pytest

from abacus.modules.evidence.item_detail import download_name

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.parametrize(
    ("title", "media", "expected"),
    [
        ("Bank statement.pdf", "application/pdf", "Bank statement.pdf"),
        ('evil"; filename="x.exe', "application/pdf", "evil_ filename_x.exe"),
        ("Résumé 2026", "application/pdf", "R_sum_ 2026.pdf"),
        ("...", "image/png", "evidence.png"),
    ],
)
def test_ac2_upload_names_are_ascii_safe(title: str, media: str, expected: str) -> None:
    assert download_name(title, 1, None, media) == expected


def test_ac2_retrieved_versions_are_named_by_version_and_period() -> None:
    assert download_name(None, 3, date(2026, 12, 31), XLSX) == "evidence-v3-2026-12-31.xlsx"
    assert download_name(None, 1, None, "application/x-unknown") == "evidence-v1.bin"
