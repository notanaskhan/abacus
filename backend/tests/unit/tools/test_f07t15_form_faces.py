"""F-07-T15 (TASK-7728; F-07 §H; DEC-4731): TPL-17's test-only faces, the part that needs no Pango.

The manifest values foot to Schedule K, each value is findable once on its own page, no field
holds a full TIN or PTIN, the blocks are C11's closed union, and the input is the same every
time (byte determinism of the render itself is `make form-fixtures`, inside the backend image).
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from pydantic import TypeAdapter

from abacus.modules.reporting.contract import DocBlock
from abacus_tools.specimens import form_faces as ff


def test_the_faces_foot_to_schedule_k() -> None:
    a = ff.amount
    assert a("k.l2") + a("k.l5") == a("an.l1") == a("m2.l3") == Decimal(1_250_000)
    assert a("an.gp") + a("an.lp_ind") + a("an.lp_pship") == a("an.l1")
    assert a("m2.l1") + a("m2.l2a") + a("m2.l3") == a("m2.l5")
    assert a("m2.l5") - a("m2.l6a") == a("m2.l9")
    assert a("l.l21") - a("m2.l9") == a("k.l18a") == Decimal(6_200)  # TPL-17: "off 6,200"
    assert a("k.l19a") == a("m2.l6a")
    quarter = Decimal("0.25")
    for box, k in (
        ("k1f.b2", "k.l2"),
        ("k1f.b5", "k.l5"),
        ("k1f.b18a", "k.l18a"),
        ("k1f.b19a", "k.l19a"),
    ):
        assert a(box) == a(k) * quarter


def test_each_value_is_once_on_its_own_page() -> None:
    for face in ff.FACES:
        texts = [f.value for f in face.fields] + [face.heading] + [f.label for f in face.fields]
        for f in face.fields:
            hits = sum(1 for t in texts if re.search(rf"(?<!\S){re.escape(f.value)}(?!\S)", t))
            assert hits == 1, f"{f.key} {f.value!r} appears {hits} times on {face.id}"


def test_no_full_tin_ptin_or_ein_on_any_face() -> None:
    full = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b|\b\d{2}-\d{7}\b|\bP\d{8}\b")
    for value in ff.values().values():
        assert not full.search(value), value


def test_the_blocks_are_c11_and_the_input_is_stable() -> None:
    TypeAdapter(list[DocBlock]).validate_python(ff.blocks())
    assert ff.content_hash() == ff.content_hash()
    assert len(ff.FACES) == 6
    keys = list(ff.values())
    assert len(keys) == len(set(keys))
    assert all(re.fullmatch(r"[a-z][a-z0-9_.]{0,79}", k) for k in keys)


def test_the_manifest_takes_each_field_from_its_page_and_refuses_ambiguity() -> None:
    page_of = {f.key: n for n, face in enumerate(ff.FACES, start=1) for f in face.fields}
    located = [ff.Located(k, p, (1.0, 2.0, 3.0, 4.0)) for k, p in page_of.items()]
    # "18,400" also sits on page 5 (line 20a): another page's hit is ignored.
    located.append(ff.Located("k.l5", 3, (9.0, 9.0, 9.0, 9.0)))
    sizes = [(612.0, 792.0)] * len(ff.FACES)
    images = [f"page-{n}.png" for n in range(1, len(ff.FACES) + 1)]
    doc = ff.manifest(located, sizes, images)
    fields = {f["id"]: f for f in doc["fields"]}  # type: ignore[union-attr]
    assert fields["k.l5"]["page"] == 2 and fields["k.l5"]["rect_pt"] == [1.0, 2.0, 3.0, 4.0]
    assert fields["p1.m3"]["diagnostic"] == "m3_required"
    assert fields["m2.l4"]["diagnostic"] == "m2_off"
    assert fields["k.l2"]["match_id"] == "sch-k-2"
    with pytest.raises(ValueError, match="2 regions"):
        ff.manifest([*located, ff.Located("k.l2", 2, (0.0, 0.0, 1.0, 1.0))], sizes, images)
    assert ff.manifest_json(doc) == ff.manifest_json(doc)


def test_nothing_here_touches_a_database_or_tenant() -> None:
    import ast
    import inspect

    for module in (ff,):
        tree = ast.parse(inspect.getsource(module))
        names = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
        }
        assert not any("kernel.db" in m or "uow" in m or "sqlalchemy" in m for m in names)
