# ac-test-author: ayushkbhatia
"""P-04-T35 (TASK-2000; ADR-160 clauses 5 and 10; SHL-09; DEC-1050): field value versions live.

Acceptance (the task row): "Halvard interest 2,190 to 2,310 shows the struck prior value, Kevin
Osei's earlier tick reads stale, and an uncited agent value cannot be ticked."

What else the contract promises (`docs/contracts/review-grammar.md`, Field provenance, part 3):
- versions newest first, each with its actor, citation note or references, `unsupported`
  computed (an agent value with no supported citation, INV-2);
- a person's edit needs a citation note and reads as theirs; a stale `seen_seq` is 409
  `field_changed` and writes nothing; where the owner checkpoints, the edit is a person's
  `human_edit` checkpoint (SHL-16);
- ticks are `field_tick` sign-offs (human only), stale once the value moves; an unsupported value
  is 422 `uncited_change` and `field.sign_off` leaves `allowed_actions`;
- flags are review notes anchored on the field;
- an unverifiable reference is 422 `uncited_change` and writes nothing;
- the flag off is 404; another firm sees nothing (404);
- FIELD-001: a write of `field_value_versions` outside `record_value` fails the build.

Boundary: `create_app()` over HTTP as each signed-in person; the seeded versions through
`review.api.record_value` as the agent and the import would write them.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.review import field_provenance as service
from abacus.modules.review.api import FieldOwner, record_value, register_field_owner
from abacus_tools.quality import banned_patterns

from .p04t28_support import PROBE, PROBED, World, agent, cite, make_world, probe
from .support import Net

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response body as the contract shapes it
HALVARD: Final = "sch_b.p1.l1.halvard"
LABEL: Final = "Taxable interest — Halvard Securities"

# --- The field owner (C3 `register_field_owner`), as an owner module registers its own ---------
EDITED: dict[tuple[uuid.UUID, str], dict[str, object]] = {}


async def _value_of(
    _tenant: TenantContext, target_id: uuid.UUID, field_key: str
) -> dict[str, object] | None:
    return EDITED.get((target_id, field_key))


async def _apply_edit(
    _tx: UnitOfWork,
    _ctx: AuthContext,
    target_id: uuid.UUID,
    field_key: str,
    value: dict[str, object],
) -> str | None:
    EDITED[(target_id, field_key)] = value
    return hashlib.sha256(f"{target_id}:{field_key}:{value}".encode()).hexdigest()


register_field_owner(
    FieldOwner(
        PROBE,
        _value_of,
        label_of=lambda key: LABEL if key == HALVARD else key,
        apply_edit=_apply_edit,
        checkpoints=True,
    )
)


@pytest.fixture
async def world(net: Net) -> World:
    return await make_world(net)


def _path(target: uuid.UUID, field_key: str = HALVARD, tail: str = "provenance") -> str:
    return f"/v1/fields/{PROBE}/{target}/{field_key}/{tail}"


def _d(v: str) -> dict[str, object]:
    return {"t": "decimal", "v": v}


async def _return(world: World) -> uuid.UUID:
    """A return on a work item Ana prepares (the `function_in: preparer` condition on edit)."""
    target = probe(world.site, (world["ana"],))
    item = await world.seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
        "VALUES ($1, $2, $3, 'tax_return', 'Form 1040 Feld', $4) RETURNING id",
        world.tenant_id,
        world.site.engagement_id,
        world.site.client_id,
        world["hannah"].user_id,
    )
    await world.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'preparer', $5)",
        world.tenant_id,
        item,
        world.site.engagement_id,
        world["ana"].user_id,
        world["hannah"].user_id,
    )
    PROBED[target] = replace(PROBED[target], work_item_id=cast(uuid.UUID, item))
    return target


async def _imported(world: World, target: uuid.UUID, v: str) -> None:
    """The engine import's version (Imported Return), as the system writes it."""
    system = TenantContext(world.tenant_id, "system", "tax.engine_import")
    async with uow(system) as tx:
        await record_value(
            tx,
            engagement_id=world.site.engagement_id,
            target_type=PROBE,
            target_id=target,
            field_key=HALVARD,
            value=_d(v),
            value_source="engine_import",
            cause="import",
        )


async def _agent_value(
    world: World, target: uuid.UUID, v: str, citations: tuple[uuid.UUID, ...]
) -> None:
    bot = await agent(world)
    async with uow(bot.tenant) as tx:
        await record_value(
            tx,
            engagement_id=world.site.engagement_id,
            target_type=PROBE,
            target_id=target,
            field_key=HALVARD,
            value=_d(v),
            value_source="agent_suggested",
            cause="suggestion_adopted",
            citation_ids=citations,
        )


async def _tray(world: World, target: uuid.UUID, who: str = "samuel") -> Body:
    found = await world.call("GET", _path(target), who)
    assert found.status_code == 200, found.text
    return cast(Body, found.json())


async def _tick(
    world: World, target: uuid.UUID, who: str, level: str, seen: str
) -> httpx.Response:
    return await world.call(
        "POST", _path(target, tail="ticks"), who, {"level": level, "seen_hash": seen}
    )


# --- The row's acceptance ------------------------------------------------------------------------


async def test_ac1_halvard_2190_to_2310_struck_prior_and_stale_tick(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    before = await _tray(world, target, "kevin")
    ticked = await _tick(world, target, "kevin", "L1_preparer", before["content_hash"])
    assert ticked.status_code == 201, ticked.text
    assert [t["stale"] for t in ticked.json()["ticks"]] == [False]

    await _agent_value(world, target, "2310", (await cite(world),))
    tray = await _tray(world, target)
    assert tray["label"] == LABEL and tray["current_seq"] == 2
    assert [v["value"]["v"] for v in tray["versions"]] == ["2310", "2190"]  # prior kept, struck
    assert tray["versions"][1]["actor_name"] == "Imported Return"
    assert tray["versions"][0]["unsupported"] is False
    [tick] = tray["ticks"]
    assert tick["signer_name"] == "Kevin Osei" and tick["initials"] == "KO"
    assert tick["stale"] is True  # "✓ KO · Sep 8 (before this change)"
    assert tick["content_hash"] != tray["content_hash"]


async def test_ac2_an_uncited_agent_value_cannot_be_ticked(world: World) -> None:
    target = await _return(world)
    await _agent_value(world, target, "2310", ())
    tray = await _tray(world, target, "kevin")
    assert tray["versions"][0]["unsupported"] is True
    assert "field.sign_off" not in tray["allowed_actions"]
    refused = await _tick(world, target, "kevin", "L1_preparer", tray["content_hash"])
    assert refused.status_code == 422 and refused.json()["detail"] == "uncited_change"
    assert (await _tray(world, target, "kevin"))["ticks"] == []


async def test_ac2_an_unverified_citation_is_unsupported_too(world: World) -> None:
    target = await _return(world)
    await _agent_value(world, target, "2310", (await cite(world, verified=False),))
    assert (await _tray(world, target))["versions"][0]["unsupported"] is True


# --- Edits -----------------------------------------------------------------------------------


async def test_ac3_a_persons_edit_needs_a_note_and_reads_as_theirs(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    empty = await world.call(
        "PUT",
        _path(target, tail="value"),
        "ana",
        {"value": _d("2310"), "citation_note": "", "seen_seq": 1},
    )
    assert empty.status_code == 422
    edited = await world.call(
        "PUT",
        _path(target, tail="value"),
        "ana",
        {"value": _d("2310"), "citation_note": "Corrected 1099-INT, box 1", "seen_seq": 1},
    )
    assert edited.status_code == 200, edited.text
    top = edited.json()["versions"][0]
    assert top["value_source"] == "human" and top["cause"] == "edit"
    assert top["actor_name"] == "Ana Cruz" and top["citation"] == "Corrected 1099-INT, box 1"
    assert top["unsupported"] is False
    assert EDITED[(target, HALVARD)] == _d("2310")  # the owner wrote its own record
    saved = await world.seed.value(
        "SELECT count(*) FROM checkpoints WHERE target_id = $1 AND cause = 'human_edit' "
        "AND author_kind = 'person' AND status = 'saved'",
        target,
    )
    assert saved == 1  # SHL-16: a person's checkpoint where the owner checkpoints


async def test_ac3_a_stale_seen_seq_is_field_changed_and_writes_nothing(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    await _agent_value(world, target, "2310", (await cite(world),))
    stale = await world.call(
        "PUT",
        _path(target, tail="value"),
        "ana",
        {"value": _d("2400"), "citation_note": "Statement p. 4", "seen_seq": 1},
    )
    assert stale.status_code == 409 and stale.json()["detail"] == "field_changed"
    assert (await _tray(world, target))["current_seq"] == 2


async def test_ac3_only_a_preparer_function_edits(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    denied = await world.call(
        "PUT",
        _path(target, tail="value"),
        "lena",
        {"value": _d("2310"), "citation_note": "Statement p. 4", "seen_seq": 1},
    )
    assert denied.status_code == 403


# --- Ticks are a person's ----------------------------------------------------------------------


async def test_ac4_the_agent_never_ticks(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    tray = await _tray(world, target)
    bot = await agent(world)
    with pytest.raises(Forbidden):
        await service.tick(
            cast(AuthContext, bot),
            PROBE,
            target,
            HALVARD,
            level=1,
            seen_hash=tray["content_hash"],
        )


async def test_ac4_a_moved_value_is_content_changed(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    seen = (await _tray(world, target, "kevin"))["content_hash"]
    await _agent_value(world, target, "2310", (await cite(world),))
    moved = await _tick(world, target, "kevin", "L1_preparer", seen)
    assert moved.status_code == 409 and moved.json()["detail"] == "content_changed"


async def test_ac4_one_person_never_ticks_a_value_at_both_levels(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    seen = (await _tray(world, target, "kevin"))["content_hash"]
    assert (await _tick(world, target, "kevin", "L1_preparer", seen)).status_code == 201
    again = await _tick(world, target, "kevin", "L2_reviewer", seen)
    assert again.status_code == 409 and again.json()["detail"] == "segregation"


# --- Flags and references ----------------------------------------------------------------------


async def test_ac5_a_flag_is_a_review_note_on_the_field(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    raised = await world.call(
        "POST",
        "/v1/review-notes",
        "samuel",
        {
            "target_type": PROBE,
            "target_id": str(target),
            "anchor": {"kind": "field", "ref": HALVARD},
            "body": "Confirm corrected 1099 replaces the original",
        },
    )
    assert raised.status_code == 201, raised.text
    [flag] = (await _tray(world, target))["flags"]
    assert flag["raised_by_initials"] == "SI" and flag["status"] == "open"
    assert flag["body"] == "Confirm corrected 1099 replaces the original"


async def test_ac6_an_unverifiable_reference_writes_nothing(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    refused = await world.call(
        "POST",
        _path(target, tail="references"),
        "ana",
        {"document_id": str(uuid.uuid4()), "page": 4, "seen_seq": 1},
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "uncited_change"
    assert (await _tray(world, target))["current_seq"] == 1


# --- Scope -------------------------------------------------------------------------------------


async def test_ac7_flag_off_and_other_firms_are_404(world: World) -> None:
    target = await _return(world)
    await _imported(world, target, "2190")
    other = await make_world(world.net, "Granite Peak Holdings")
    assert (await other.call("GET", _path(target), "samuel")).status_code == 404
    await world.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'review.grammar_api'",
        world.tenant_id,
    )
    forget_flags()
    assert (await world.call("GET", _path(target), "samuel")).status_code == 404


# --- FIELD-001 ---------------------------------------------------------------------------------


def test_ac8_field_001_fails_a_write_outside_record_value(tmp_path: Path) -> None:
    def found(text: str, rel: str = "src/abacus/modules/ledger/x.py") -> list[str]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return [v.rule_id for v in banned_patterns.scan(tmp_path) if v.path == rel]

    assert "FIELD-001" not in found("VALUE = 1\n")
    assert "FIELD-001" in found('SQL = "INSERT INTO field_value_versions (seq) VALUES (1)"\n')
    assert "FIELD-001" in found(
        "from sqlalchemy import insert\n"
        "from abacus.modules.review.models import FieldValueVersion\n"
        "STMT = insert(FieldValueVersion)\n"
    )
    assert "FIELD-001" not in found(
        'SQL = "INSERT INTO field_value_versions (seq) VALUES (1)"\n',
        "src/abacus/modules/review/field_values.py",
    )
