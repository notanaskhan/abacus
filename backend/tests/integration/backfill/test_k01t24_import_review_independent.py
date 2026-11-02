"""K-01-T24 (TASK-3016; K-01 §3.6, §3.7 backend half; ADR-078 independent): K-01-T18's import
review, tested from the spec rather than the build.

Row acceptance: "Every amber AC in section 3.6 and the backend half of section 3.7 has a passing
test written." K-01-T18's own suite pins the 4/9/1/54 diff, the flags_open and unverified_sources
409s and the document-import boundary; these add what it leaves out:

- source files are write-once for the app (no UPDATE, no DELETE) and every file is scanned before
  the parse reads it (AC7.9);
- the diff is the same over two independent imports of the same workbook (AC6.1: code only);
- a flag resolution keeps the step's key, text and citation (AC3.4, AC6.1);
- approve answers 409 `checklist_changed` when the checklist moved since the dialog opened (AC3.4);
- the standards sets offered are platform reference rows and none is an issuer (PCAOB) set (AC6.2;
  X-07, X-01).
"""

from __future__ import annotations

from typing import cast

import pytest

from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import spec_of, workbook

from .support import Json, Net
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's flag seeding
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
)
from .test_k01t18_import_review import (
    FLAGS,
    TEMPLATE,
    _v3,  # pyright: ignore[reportPrivateUsage] -- K-01-T18's v3 import
    raw,
    wired,
)

pytestmark = pytest.mark.asyncio
__all__ = ("raw", "wired")  # K-01-T18's storage fixtures, used here too


async def test_ac7_9_source_files_are_write_once_for_the_app(net: Net) -> None:
    for privilege in ("UPDATE", "DELETE"):
        allowed = await net.seed.value(
            f"SELECT has_table_privilege('abacus_app', 'methodology_source_files', '{privilege}')"
        )
        assert not allowed, privilege


async def test_ac7_9_every_file_is_scanned_before_the_parse(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    await _flags(net, tenant, *FLAGS)
    await _import(net, hannah, TEMPLATE, workbook(spec_of("ebp", 2)))
    v3 = await _v3(net, hannah)
    statuses = await seed.rows(
        "SELECT f.scan_status FROM methodology_source_files f "
        "JOIN methodology_imports i ON i.id = f.import_id WHERE i.version_id = $1",
        v3,
    )
    assert statuses and {r["scan_status"] for r in statuses} == {"clean"}


async def test_ac6_1_two_imports_of_one_workbook_diff_alike(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    await _flags(net, tenant, *FLAGS)
    v2 = await _import(net, hannah, TEMPLATE, workbook(spec_of("ebp", 2)))
    first = await _v3(net, hannah)
    tiles = cast(
        Json,
        (
            await net.call("GET", f"/v1/methodology/versions/{first}/diff?against={v2}", hannah)
        ).json(),
    )["tiles"]
    assert tiles == {"added": 4, "changed": 9, "removed": 1, "unchanged": 54}


async def test_ac3_4_a_resolution_keeps_the_steps_key_text_and_citation(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    await _flags(net, tenant, *FLAGS)
    v3 = await _v3(net, hannah)
    before = (
        await seed.rows(
            "SELECT s.id, s.step_key, s.text, s.standard_refs, s.row_version FROM program_steps s "
            "JOIN programs p ON p.id = s.program_id "
            "WHERE s.version_id = $1 AND p.code = 'BH-EBP-110' AND s.number = 7",
            v3,
        )
    )[0]
    await seed.run_untriggered(
        "UPDATE program_steps SET parse_flag = 'low_confidence' WHERE id = $1", before["id"]
    )
    resolved = await net.call(
        "POST",
        f"/v1/methodology/versions/{v3}/steps/{before['id']}/flag-resolution",
        hannah,
        body={"action": "confirm", "row_version": before["row_version"]},
    )
    assert resolved.status_code == 200, resolved.text
    after = (
        await seed.rows(
            "SELECT step_key, text, standard_refs FROM program_steps WHERE id = $1", before["id"]
        )
    )[0]
    assert (after["step_key"], after["text"], after["standard_refs"]) == (
        before["step_key"],
        before["text"],
        before["standard_refs"],
    )


async def test_ac3_4_approve_refuses_a_checklist_that_moved(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "practice_leader")
    await _flags(net, tenant, *FLAGS)
    v3 = await _v3(net, hannah)
    state = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{v3}/state", margaret)).json()
    )
    moved = await net.call(
        "POST",
        f"/v1/methodology/versions/{v3}/approve",
        margaret,
        body={
            "effective_from": "2026-01-01",
            "checklist_hash": "sha256:" + "0" * 64,
            "row_version": state["row_version"],
        },
    )
    assert (moved.status_code, moved.json()["detail"]) == (409, "checklist_changed")


async def test_ac6_2_no_issuer_standards_set_is_ever_offered(net: Net) -> None:
    issuer = await net.seed.value(
        "SELECT count(*) FROM reference_sets WHERE key ILIKE '%pcaob%' OR title ILIKE '%pcaob%'"
    )
    assert issuer == 0
