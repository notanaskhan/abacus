"""F-03-T29 (ADR-139, P-36): "Cursors are opaque AES-GCM tokens, counts ignore the tile filter,
and a unit test fails any facts field holding free text." The counts and totals run against
Postgres in tests/integration/test_listing.py."""

from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, select
from sqlalchemy.dialects import postgresql

from abacus.api.app import (
    _coded,  # pyright: ignore[reportPrivateUsage]  # the handler's body builder
)
from abacus.kernel import listing
from abacus.kernel.errors import (
    DomainConflict,
    DomainInvalid,
    FactsNotIdentifiers,
    check_facts,
)

TENANT = uuid4()
OTHER_TENANT = uuid4()


def _cursor(key: object = "Ridgeline Property Partners, LP", row_id: str = "r-9") -> str:
    return listing.encode_cursor(
        listing.Position(key=key, id=row_id),  # type: ignore[arg-type]  # a scalar sort key
        tenant_id=TENANT,
        resource="clients",
        query=listing.query_hash(office="den", sort="name:asc"),
    )


class TestCursor:
    def test_round_trip(self) -> None:
        token = _cursor()
        position = listing.decode_cursor(
            token,
            tenant_id=TENANT,
            resource="clients",
            query=listing.query_hash(office="den", sort="name:asc"),
        )
        assert position == listing.Position(key="Ridgeline Property Partners, LP", id="r-9")

    def test_opaque_the_sort_key_is_not_readable(self) -> None:
        token = _cursor()
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        assert b"Ridgeline" not in raw
        assert "Ridgeline" not in token
        assert b"r-9" not in raw

    def test_two_cursors_for_one_position_differ(self) -> None:
        assert _cursor() != _cursor()

    @pytest.mark.parametrize(
        ("tenant", "resource", "query"),
        [
            (OTHER_TENANT, "clients", listing.query_hash(office="den", sort="name:asc")),
            (TENANT, "engagements", listing.query_hash(office="den", sort="name:asc")),
            (TENANT, "clients", listing.query_hash(office="chi", sort="name:asc")),
        ],
    )
    def test_bound_to_tenant_resource_and_query(
        self, tenant: object, resource: str, query: str
    ) -> None:
        with pytest.raises(listing.CursorInvalid):
            listing.decode_cursor(_cursor(), tenant_id=tenant, resource=resource, query=query)  # type: ignore[arg-type]  # a UUID

    @pytest.mark.parametrize("token", ["", "not-a-cursor", "AA", "x" * 80])
    def test_garbage_is_invalid(self, token: str) -> None:
        with pytest.raises(listing.CursorInvalid):
            listing.decode_cursor(token, tenant_id=TENANT, resource="clients", query="q")

    def test_a_tampered_cursor_is_invalid(self) -> None:
        token = _cursor()
        raw = bytearray(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        raw[-1] ^= 0x01
        tampered = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode()
        with pytest.raises(listing.CursorInvalid):
            listing.decode_cursor(
                tampered,
                tenant_id=TENANT,
                resource="clients",
                query=listing.query_hash(office="den", sort="name:asc"),
            )

    def test_cursor_invalid_is_a_422_code(self) -> None:
        assert issubclass(listing.CursorInvalid, DomainInvalid)
        assert listing.CursorInvalid.code == "cursor_invalid"

    def test_sort_keys_are_scalars(self) -> None:
        with pytest.raises(TypeError):
            _cursor(key={"name": "x"})


class TestPages:
    @pytest.mark.parametrize(("asked", "got"), [(None, 50), (0, 1), (-5, 1), (25, 25), (500, 200)])
    def test_limit(self, asked: int | None, got: int) -> None:
        assert listing.clamp_limit(asked) == got

    def test_page_of_splits_the_extra_row_into_the_next_position(self) -> None:
        rows = [("Alder", "1"), ("Birch", "2"), ("Cedar", "3")]
        page, nxt = listing.page_of(rows, limit=2, key=lambda r: r[0], id_of=lambda r: r[1])
        assert page == rows[:2]
        assert nxt == listing.Position(key="Birch", id="2")
        last, none = listing.page_of(rows[:2], limit=2, key=lambda r: r[0], id_of=lambda r: r[1])
        assert last == rows[:2]
        assert none is None

    def test_keyset_compares_the_pair_and_asks_one_row_more(self) -> None:
        t = Table("t", MetaData(), Column("id", String), Column("name", String))
        stmt = listing.keyset(
            select(t),
            sort=t.c.name,
            id_column=t.c.id,
            after=listing.Position(key="Birch", id="2"),
            limit=50,
        )
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "(t.name, t.id) > (" in sql
        assert "ORDER BY t.name ASC, t.id ASC" in sql
        assert "LIMIT" in sql
        assert 51 in stmt.compile().params.values()

    def test_keyset_descending(self) -> None:
        t = Table("t", MetaData(), Column("id", String), Column("n", Integer))
        stmt = listing.keyset(
            select(t),
            sort=t.c.n,
            id_column=t.c.id,
            after=listing.Position(key=3, id="b"),
            descending=True,
        )
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "(t.n, t.id) < (" in sql
        assert "ORDER BY t.n DESC, t.id DESC" in sql

    def test_envelope_carries_a_sealed_cursor_only_when_there_is_more(self) -> None:
        q = listing.query_hash(sort="name:asc")
        done = listing.envelope(
            [1, 2], next_position=None, tenant_id=TENANT, resource="r", query=q, total=(2, False)
        )
        assert done.model_dump() == {
            "items": [1, 2],
            "next_cursor": None,
            "total": 2,
            "total_capped": False,
            "counts": {},
            "facets": {},
        }
        more = listing.envelope(
            [1],
            next_position=listing.Position(key="a", id="1"),
            tenant_id=TENANT,
            resource="r",
            query=q,
            total=(10_000, True),
            counts={"open": 3},
        )
        assert more.next_cursor is not None
        assert more.total_capped is True
        assert more.counts == {"open": 3}


class TestFacts:
    @pytest.mark.parametrize(
        "facts",
        [
            {"gate": "G3"},
            {"item": "AJE-06", "count": 4, "late": True},
            {"engagement_id": str(uuid4())},
            {"status": "in_review", "action": "evidence.read"},
        ],
    )
    def test_identifiers_codes_ints_and_bools_pass(self, facts: dict[str, object]) -> None:
        assert check_facts(facts) == facts

    @pytest.mark.parametrize(
        "facts",
        [
            {"reason": "Gate G3 failed for client Acme Corp"},
            {"client": "Copperleaf Coffee Roasters, Inc."},
            {"note": ""},
            {"gate": "G3 "},
            {"amount": 12.5},
            {"list": ["G1", "G2"]},
            {"Gate": "G3"},
            {"x" * 41: 1},
        ],
    )
    def test_free_text_or_other_shapes_fail(self, facts: dict[str, object]) -> None:
        with pytest.raises(FactsNotIdentifiers):
            check_facts(facts)

    def test_an_error_refuses_free_text_facts_when_raised(self) -> None:
        class GateUnmet(DomainConflict):
            code = "gate_unmet"

        with pytest.raises(FactsNotIdentifiers):
            GateUnmet(facts={"why": "the partner has not signed"})

    def test_the_response_body_is_the_code_and_its_facts(self) -> None:
        class GateUnmet(DomainConflict):
            code = "gate_unmet"

        assert _coded(GateUnmet(facts={"gate": "G3"})) == {
            "detail": "gate_unmet",
            "facts": {"gate": "G3"},
        }
        assert _coded(GateUnmet()) == {"detail": "gate_unmet"}
        assert json.dumps(_coded(GateUnmet(facts={"n": 2})))
