"""P-04-T14: `review.hashing`, RFC 8785 canonical JSON and SHA-256 (DEC-215).

"Golden vectors hash identically through the helper and the owner adapters." The vectors'
canonical forms are written by hand (the two RFC 8785 section 3.2.3 examples are the RFC's own),
so the test checks the helper against the rules, not against itself.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from abacus.modules.review.api import Json, NotCanonical, canonical_json, content_hash
from abacus.modules.workpapers.service import content_hash as workpaper_hash

GOLDEN = Path(__file__).parent / "golden" / "hash_vectors.json"
Vector = dict[str, str | None]
VECTORS = cast(list[Vector], json.loads(GOLDEN.read_text())["vectors"])
# Each owner adapter that hashes reviewable content: it must agree with the helper.
ADAPTERS: dict[str, Callable[[dict[str, object]], str]] = {"workpaper": workpaper_hash}


def _input(v: Vector) -> Json:
    return cast(Json, json.loads(str(v["input"])))


@pytest.mark.parametrize("vector", VECTORS, ids=[str(v["name"]) for v in VECTORS])
def test_golden_vectors_canonicalise_and_hash_as_written(vector: Vector) -> None:
    assert canonical_json(_input(vector)).decode("utf-8") == vector["canonical"]
    assert content_hash(_input(vector)) == vector["sha256"]
    canonical = str(vector["canonical"]).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == vector["sha256"]


@pytest.mark.parametrize(
    "vector",
    [v for v in VECTORS if v["owner"]],
    ids=[str(v["name"]) for v in VECTORS if v["owner"]],
)
def test_owner_adapters_hash_golden_vectors_identically(vector: Vector) -> None:
    adapter = ADAPTERS[str(vector["owner"])]
    assert adapter(cast(dict[str, object], _input(vector))) == content_hash(_input(vector))
    assert adapter(cast(dict[str, object], _input(vector))) == vector["sha256"]


def test_ascii_workpaper_hashes_are_unchanged_by_the_move_to_rfc_8785() -> None:
    """DEC-215: for ASCII content without floats the old sorted compact `json.dumps` and the
    canonical form are the same bytes, so existing sign-offs on such papers stay current."""
    vector = next(v for v in VECTORS if v["name"] == "workpaper_ascii")
    old = json.dumps(_input(vector), sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(old).hexdigest() == vector["sha256"]


def test_member_order_and_container_type_do_not_change_the_hash() -> None:
    assert content_hash({"b": [1, 2], "a": "x"}) == content_hash({"a": "x", "b": (1, 2)})
    assert content_hash([1, 2]) != content_hash([2, 1])


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        -float("inf"),
        Decimal("2310.00"),  # money is hashed as a string
        2**53,  # not exact as a double
        -(2**53),
        {1: "x"},  # names are strings
        "\ud800",  # a lone surrogate
        {"when": object()},
        {1.5},
    ],
)
def test_values_without_an_exact_canonical_form_are_refused(value: object) -> None:
    with pytest.raises(NotCanonical):
        canonical_json(cast(Json, value))


def test_escapes_follow_rfc_8785() -> None:
    assert canonical_json('\u0000\u001f\b\t\n\f\r"\\/\u2028é') == (
        '"\\u0000\\u001f\\b\\t\\n\\f\\r\\"\\\\/\u2028é"'.encode()
    )
    assert canonical_json([None, True, False, 0, -0.0, 9007199254740991]) == (
        b"[null,true,false,0,0,9007199254740991]"
    )
