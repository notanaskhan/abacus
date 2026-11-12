"""P-02-T07 (TASK-7616; DEC-4613): the seven owners register their C15 v1 projections, each in its
canonical group with a read action and a screen target, the return as `tri`; and the code-only
scrub keeps every TIN, long digit run and amount out of an indexed string."""

from __future__ import annotations

import pytest

import abacus.api.app  # noqa: F401  # pyright: ignore[reportUnusedImport] -- imports every module, so each registers its projection
from abacus.modules.platform.search import scrub, spec

EXPECTED = {
    "client": ("clients", "client.read", "client", "CLI-02", "confidential"),
    "tax_return": ("returns", "tax_return.read", "work_item", "TAX-02", "tri"),
    "assurance": ("audits", "engagement.read", "work_item", "AUD-02", "confidential"),
    "binder": ("binders", "binder.read", "engagement", "BND-02", "confidential"),
    "document": ("files", "evidence.read", "client", "FIL-01", "confidential"),
    "inbox_thread": ("inbox", "inbox.read", "client", "INB-01", "confidential"),
    "todo": ("todos", "todo.read", "engagement", "SHL-17", "confidential"),
}


@pytest.mark.parametrize("object_type", sorted(EXPECTED))
def test_each_owner_registers_its_projection(object_type: str) -> None:
    found = spec.projection(object_type)
    assert found is not None, object_type
    assert (
        found.group,
        found.read_action,
        found.scope_kind,
        found.target,
        found.data_class,
    ) == EXPECTED[object_type]
    assert found.list_ids is not None
    assert found.triggers, object_type


def test_the_groups_come_in_canonical_order() -> None:
    groups = [p.group for p in spec.projections() if p.object_type in EXPECTED]
    assert groups == sorted(groups, key=spec.GROUP_ORDER.index)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Feld 900-45-6789 W-2.pdf", "Feld ••• W-2.pdf"),
        ("EIN 12-3456789 letter", "EIN ••• letter"),
        ("Acct 0009004567890 statement", "Acct ••• statement"),
        ("Invoice $48,600.00 paid", "Invoice ••• paid"),
        ("Net assets 16,812,400", "Net assets •••"),
        ("PayGrid Contribution Detail 2025.xlsx", "PayGrid Contribution Detail 2025.xlsx"),
        ("BH-FS-430", "BH-FS-430"),
        ("Ridgeline\u202e Property\u200b Partners, LP", "Ridgeline Property Partners, LP"),
    ],
)
def test_the_scrub_masks_tins_digits_and_amounts(raw: str, clean: str) -> None:
    assert scrub.clean(raw) == clean
