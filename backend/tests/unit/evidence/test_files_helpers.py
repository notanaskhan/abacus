"""The Files screen's pure helpers, without a database (P-06; FIL-01, FIL-02; Q-03-T147).

The integration suites read folders through the routes; these pin, on the unit suites alone, what
a mutation run decides: which folder refs parse, how virtual splits map to page ranges, which rows
a folder lists, how a tree node is built, and how the access log names its actors.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.evidence import files

files_Folder = files._Folder  # pyright: ignore[reportPrivateUsage] -- the helper under test
files_virtual = files._virtual  # pyright: ignore[reportPrivateUsage] -- the helper under test
files_Row = files._Row  # pyright: ignore[reportPrivateUsage] -- the helper under test
files_documents = files._documents  # pyright: ignore[reportPrivateUsage] -- the helper under test
files_name = files._name  # pyright: ignore[reportPrivateUsage] -- the helper under test
files_node = files._node  # pyright: ignore[reportPrivateUsage] -- the helper under test
files_actor = files._actor  # pyright: ignore[reportPrivateUsage] -- the helper under test
files_is_uuid = files._is_uuid  # pyright: ignore[reportPrivateUsage] -- the helper under test

WI = uuid.UUID("00000000-0000-4000-8000-0000000000f1")
CLIENT = uuid.UUID("00000000-0000-4000-8000-0000000000c1")
ANA = uuid.UUID("00000000-0000-4000-8000-000000000001")


# --- folder refs ---------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", files.FOLDER_KINDS)
def test_work_item_folder_ref(kind: str) -> None:
    assert files.parse_folder_ref(f"folder:{WI}:{kind}") == files_Folder(None, WI, kind)  # type: ignore[arg-type] -- a FolderKind from FOLDER_KINDS


def test_permanent_file_ref() -> None:
    assert files.parse_folder_ref(f"permanent:{CLIENT}") == files_Folder(CLIENT, None, None)


def test_permanent_folder_ref() -> None:
    assert files.parse_folder_ref(f"permanent:{CLIENT}:workpapers") == files_Folder(
        CLIENT, None, "workpapers"
    )


@pytest.mark.parametrize(
    "ref",
    [
        "",
        "folder",
        f"folder:{WI}",
        f"folder:{WI}:unknown",
        f"folder:{WI}:workpapers:extra",
        "folder:not-a-uuid:workpapers",
        f"permanent:{CLIENT}:unknown",
        f"permanent:{CLIENT}:workpapers:extra",
        "permanent:not-a-uuid",
        "permanent:not-a-uuid:workpapers",
        f"client:{CLIENT}",
        f"Folder:{WI}:workpapers",
    ],
)
def test_anything_else_is_not_found(ref: str) -> None:
    with pytest.raises(NotFound):
        files.parse_folder_ref(ref)


# --- virtual splits ------------------------------------------------------------------------------


@dataclass
class _Range:
    lower: int | None
    upper: int | None
    upper_inc: bool = False


@dataclass
class _Version:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    page_range: _Range | None = None
    virtual_label: str | None = None
    virtual_amount: Decimal | None = None
    parent_version_id: uuid.UUID | None = None
    supersedes_version_id: uuid.UUID | None = None
    version_no: int = 1
    display_name: str | None = None


def test_virtual_children_in_page_order_with_ranges() -> None:
    a = _Version(
        page_range=_Range(5, 8), virtual_label="Invoice 2", virtual_amount=Decimal("10.50")
    )
    b = _Version(page_range=_Range(1, 3, upper_inc=True), virtual_label="Invoice 1")
    out = files_virtual([a, b])  # type: ignore[list-item] -- stand-in versions
    assert [(c.id, c.label, c.first_page, c.last_page, c.amount) for c in out] == [
        (b.id, "Invoice 1", 1, 3, None),
        (a.id, "Invoice 2", 5, 7, Decimal("10.50")),
    ]


def test_virtual_child_without_a_range_is_page_one() -> None:
    plain = _Version()
    [out] = files_virtual([plain])  # type: ignore[list-item] -- stand-in versions
    assert (out.label, out.first_page, out.last_page) == ("", 1, 1)


def test_virtual_child_open_ranges() -> None:
    no_upper = _Version(page_range=_Range(4, None))
    no_lower = _Version(page_range=_Range(None, 6))
    single = _Version(page_range=_Range(9, 10))
    empty = _Version(page_range=_Range(3, 3))
    out = files_virtual([no_upper, no_lower, single, empty])  # type: ignore[list-item] -- stand-in versions
    pages = {c.id: (c.first_page, c.last_page) for c in out}
    assert pages[no_upper.id] == (4, 4)
    assert pages[no_lower.id] == (1, 5)
    assert pages[single.id] == (9, 9)
    assert pages[empty.id] == (3, 3)
    assert [c.id for c in out] == [no_lower.id, empty.id, no_upper.id, single.id]


# --- which rows a folder lists -------------------------------------------------------------------


@dataclass
class _Item:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    title: str = "Bank statement"


def _row(item: _Item, version: _Version) -> files_Row:
    return files_Row(item, version)  # type: ignore[arg-type] -- stand-in records


def test_documents_lists_the_newest_version_of_each_item() -> None:
    item = _Item()
    v1, v2 = _Version(version_no=1), _Version(version_no=2)
    other = _Item()
    w1 = _Version(version_no=1)
    listed, children, replaced = files_documents([_row(item, v2), _row(item, v1), _row(other, w1)])
    assert [r.version for r in listed] == [v2, w1]
    assert children == {}
    assert replaced == {}


def test_documents_keeps_a_superseded_version_beside_its_replacement() -> None:
    item = _Item()
    old = _Version(version_no=1)
    new = _Version(version_no=2, supersedes_version_id=old.id)
    listed, _, replaced = files_documents([_row(item, old), _row(item, new)])
    assert [r.version for r in listed] == [new, old]
    assert replaced == {old.id: new}


def test_documents_never_lists_the_newest_twice() -> None:
    item = _Item()
    first = _Version(version_no=1)
    # A version that names itself the replacement of the newest: still listed once.
    newest = _Version(version_no=3)
    third = _Version(version_no=2, supersedes_version_id=newest.id)
    listed, _, _ = files_documents([_row(item, first), _row(item, newest), _row(item, third)])
    assert [r.version for r in listed] == [newest]


def test_documents_puts_virtual_children_under_their_parent() -> None:
    item = _Item()
    parent = _Version(version_no=1)
    c1 = _Version(parent_version_id=parent.id, version_no=5)
    c2 = _Version(parent_version_id=parent.id, version_no=6)
    listed, children, _ = files_documents([_row(item, c1), _row(item, parent), _row(item, c2)])
    assert [r.version for r in listed] == [parent]
    assert children == {parent.id: [c1, c2]}


def test_name_prefers_the_version_display_name() -> None:
    item = _Item(title="Title")
    assert files_name(_Version(display_name="Shown"), item) == "Shown"  # type: ignore[arg-type] -- stand-in records
    assert files_name(_Version(), item) == "Title"  # type: ignore[arg-type] -- stand-in records


# --- tree nodes ----------------------------------------------------------------------------------


def test_node_expanded_with_children() -> None:
    leaf = files_node(
        "folder:x:workpapers", "folder", "Workpapers", 2, [], folder_kind="workpapers"
    )
    node = files_node("work_item:x", "work_item", "2025 audit", 2, [leaf])
    assert node.model_dump() == {
        "ref": "work_item:x",
        "kind": "work_item",
        "label": "2025 audit",
        "folder_kind": None,
        "count": 2,
        "has_children": True,
        "on_hold": False,
        "locked": False,
        "children": [leaf.model_dump()],
    }
    assert leaf.has_children is False
    assert leaf.folder_kind == "workpapers"


def test_node_collapsed_keeps_has_children() -> None:
    leaf = files_node("f", "folder", "F", 0, [])
    node = files_node("c", "client", "Client", 1, [leaf], expanded=False)
    assert node.children == []
    assert node.has_children is True


# --- access log actors ---------------------------------------------------------------------------


@dataclass
class _Audit:
    actor_kind: str
    actor_id: str


def test_actor_names() -> None:
    names = {ANA: "Ana Alvarez"}
    assert files_actor(_Audit("agent", str(ANA)), names) == "Accrued Agent"  # type: ignore[arg-type] -- a stand-in row
    assert files_actor(_Audit("system", "system:x"), names) == "Accrued"  # type: ignore[arg-type] -- a stand-in row
    assert files_actor(_Audit("human", str(ANA)), names) == "Ana Alvarez"  # type: ignore[arg-type] -- a stand-in row
    assert files_actor(_Audit("human", str(uuid.UUID(int=5))), names) == "Former member"  # type: ignore[arg-type] -- a stand-in row
    assert files_actor(_Audit("human", "not-a-uuid"), names) == "Former member"  # type: ignore[arg-type] -- a stand-in row


def test_is_uuid() -> None:
    assert files_is_uuid(str(ANA)) is True
    assert files_is_uuid("system:x") is False
    assert files_is_uuid("") is False
