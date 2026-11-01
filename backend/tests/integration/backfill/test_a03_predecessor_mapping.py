"""A mapping run on a predecessor auditor's mapping file (TASK-2718; DEC-1769; A-03 §4.2
`mapping_sets.prior_source`; QA-7) over HTTP against Postgres and S3.

On the A-02 books (six accounts) with the A-03-T08 groupings: the file maps 1210 by label,
2500 by key and 1900 (in no range) by label, and names a line the version does not have for
3000. So three accounts read "prior year · High", 1220, 1230 and 3000 fall to the number ranges,
and nothing waits in Needs review. The source and the parsed keys are fixed on the set; a file
source without a file, a file without a file source, another engagement's file and a sheet with
no FS-line column are refused before anything is written.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any, Final, cast

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import uow
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import NewItem, Provenance, add_version, stage_content
from abacus.modules.ledger.api import import_grouping_set, publish_version

from .support import Net
from .tb_support import Books, books

Json = dict[str, Any]  # Any: JSON bodies
BUCKET: Final = "task2718-predecessor-mapping"
MASTER: Final = b"task2718-predecessor-mapping-master-key-0123"
CSV: Final = (
    "grouping_key,grouping_label,class,fs_line_key,fs_line_label,normal_balance,"
    "account_from,account_to\n"
    "investments,Investments,assets,investments,Investments at fair value,debit,1200,1299\n"
    "liabilities,Liabilities,liabilities,loans,Loans payable,credit,2000,2999\n"
    "net_assets,Net assets,equity,net_assets,Net assets available for benefits,credit,3000,3999\n"
)
PREDECESSOR: Final = (
    b"Account,Account name,FS line\n"
    b"1210,KRS 500 Index,Investments at fair value\n"
    b"1900,Suspense,Loans payable\n"
    b"2500,Loan payable,loans\n"
    b"3000,Net assets,Members' equity\n"
)
NO_LINE_COLUMN: Final = b"Account,Account name\n1210,KRS 500 Index\n"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    forget_flags()
    yield
    forget_flags()
    storage.reset_storage()
    reset_key_service()


async def _world(net: Net) -> tuple[Books, uuid.UUID, str]:
    world = await books(net)
    for flag in ("ledger.tb_mapping", "review.grammar_api"):
        await net.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'a03', 'TASK-2718') ON CONFLICT DO NOTHING",
            world.tenant_id,
            flag,
        )
    margaret = await net.seed.person(world.tenant_id, "quality_partner")
    person = TenantContext(world.tenant_id, "human", str(margaret.user_id))
    async with uow(person) as tx:
        version = await import_grouping_set(
            tx, tenant_id=world.tenant_id, key="bh-fs", name="BH FS groupings", text=CSV,
            user_id=margaret.user_id,
        )  # fmt: skip
    async with uow(person) as tx:
        await publish_version(
            tx,
            version_id=version,
            user_id=margaret.user_id,
            actor_kind="human",
            effective_from=date(2026, 9, 1),
        )
    tb_id = await world.adopted()
    return world, tb_id, f"/v1/engagements/{world.site.engagement_id}/mapping-sets"


async def _file(world: Books, engagement_id: uuid.UUID, content: bytes, title: str) -> str:
    stored = await stage_content(world.tenant_id, content)
    async with uow(TenantContext(world.tenant_id, "system", "test-seed")) as tx:
        ref = await add_version(
            tx,
            engagement_id=engagement_id,
            item=NewItem(title=title),
            stored=stored,
            media_type="text/csv",
            provenance=Provenance(source="upload", method="uploaded"),
        )
    return str(ref.id)


async def test_ac1_the_predecessor_file_maps_by_prior_year_then_ranges(net: Net) -> None:
    world, tb_id, base = await _world(net)
    file = await _file(world, world.site.engagement_id, PREDECESSOR, "FY2024 mapping.csv")
    ran = await net.call(
        "POST",
        base,
        world.senior,
        body={
            "trial_balance_id": str(tb_id),
            "prior_source": "predecessor_file",
            "predecessor_evidence_version_id": file,
        },
    )
    assert ran.status_code == 202, ran.text
    msid = cast(Json, ran.json())["mapping_set_id"]
    body = cast(Json, (await net.call("GET", f"/v1/mapping-sets/{msid}", world.senior)).json())
    rows = {r["account_code"]: (r["method"], r["fs_line_label"]) for r in body["rows"]}
    assert rows == {
        "1210": ("prior_year_match", "Investments at fair value"),
        "1220": ("number_range", "Investments at fair value"),
        "1230": ("number_range", "Investments at fair value"),
        "1900": ("prior_year_match", "Loans payable"),
        "2500": ("prior_year_match", "Loans payable"),
        "3000": ("number_range", "Net assets available for benefits"),
    }
    summary = body["summary"]
    assert summary["prior_source"] == "predecessor_file"
    entity = await net.seed.value(
        "SELECT ce.name FROM client_entities ce JOIN engagements e "
        "ON e.client_entity_id = ce.id WHERE e.id = $1",
        world.site.engagement_id,
    )
    assert summary["entity_name"] == entity  # DEC-1770: the entity's name, not the TB's label
    tallies = summary["tallies"]
    assert (tallies["prior_year_match"], tallies["number_range"], tallies["need_review"]) == (
        3,
        3,
        0,
    )
    stored = await net.seed.rows(
        "SELECT prior_source, predecessor_evidence_version_id::text AS file, predecessor_keys "
        "FROM mapping_sets WHERE id = $1",
        uuid.UUID(msid),
    )
    assert [(r["prior_source"], r["file"]) for r in stored] == [("predecessor_file", file)]


async def test_ac2_the_source_and_the_file_must_agree(net: Net) -> None:
    world, tb_id, base = await _world(net)
    file = await _file(world, world.site.engagement_id, PREDECESSOR, "FY2024 mapping.csv")
    for body in (
        {"trial_balance_id": str(tb_id), "prior_source": "predecessor_file"},
        {"trial_balance_id": str(tb_id), "predecessor_evidence_version_id": file},
        {
            "trial_balance_id": str(tb_id),
            "prior_source": "none",
            "predecessor_evidence_version_id": file,
        },
    ):
        refused = await net.call("POST", base, world.senior, body=body)
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"] == "predecessor_file_mismatch"
    assert (
        await net.seed.value(
            "SELECT count(*) FROM mapping_sets WHERE trial_balance_id = $1", tb_id
        )
        == 0
    )


async def test_ac3_an_unreadable_sheet_or_another_engagements_file_is_refused(net: Net) -> None:
    world, tb_id, base = await _world(net)
    sheet = await _file(world, world.site.engagement_id, NO_LINE_COLUMN, "Accounts.csv")
    refused = await net.call(
        "POST",
        base,
        world.senior,
        body={
            "trial_balance_id": str(tb_id),
            "prior_source": "predecessor_file",
            "predecessor_evidence_version_id": sheet,
        },
    )
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"] == "predecessor_unreadable"
    other = await net.seed.site(world.tenant_id, world.partner.user_id, "other-books")
    elsewhere = await _file(world, other.engagement_id, PREDECESSOR, "FY2024 mapping.csv")
    hidden = await net.call(
        "POST",
        base,
        world.senior,
        body={
            "trial_balance_id": str(tb_id),
            "prior_source": "predecessor_file",
            "predecessor_evidence_version_id": elsewhere,
        },
    )
    assert hidden.status_code == 404, hidden.text
    assert (
        await net.seed.value(
            "SELECT count(*) FROM mapping_sets WHERE trial_balance_id = $1", tb_id
        )
        == 0
    )


async def test_ac4_none_maps_by_ranges_only(net: Net) -> None:
    world, tb_id, base = await _world(net)
    ran = await net.call(
        "POST", base, world.senior, body={"trial_balance_id": str(tb_id), "prior_source": "none"}
    )
    assert ran.status_code == 202, ran.text
    msid = cast(Json, ran.json())["mapping_set_id"]
    body = cast(Json, (await net.call("GET", f"/v1/mapping-sets/{msid}", world.senior)).json())
    assert body["summary"]["prior_source"] == "none"
    assert body["summary"]["tallies"]["prior_year_match"] == 0
