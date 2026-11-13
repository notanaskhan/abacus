"""A-05-T16 (TASK-5308; A-05 §3 F2; DV-EBP-02-1, DV-EBP-02-6; DEC-2489): the keyed SPD path.

Against Postgres and the S3 gateway. A person keys what the SPD says for a provision, with the
words on the page that say it and a note; the quote is verified on the document's word layer (C4)
before anything is kept. Code then compares it with the paper's value: c's SPD conflict comes from
the live service, not a fixture. The EBP-02 paper and its version are stubbed at `workpapers.api`.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from abacus.modules.assurance import ebp_provisions
from abacus.modules.assurance.compute.ebp.provisions import BY_KEY
from abacus.modules.evidence.words import words_upload
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Firm, Seeder, as_version, make_firm

SPD = positioned_pdf(
    [
        [(72.0, 700.0, "Summary Plan Description")],
        [(72.0, 700.0, "Entry dates: the first day of each calendar quarter")],
    ]
)
ENTRY = BY_KEY["entry_dates"]


@pytest.fixture
async def world(seed: Seeder, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    firm = await make_firm(seed)
    client_id = await seed.id(
        "SELECT client_id FROM engagements WHERE id = $1", firm.engagement_id
    )
    work_item = await seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, period_start, "
        "period_end, created_by) VALUES ($1, $2, $3, 'tax_return', 'Plan audit', '2025-01-01', "
        "'2025-12-31', $4) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        client_id,
        firm.user_id,
    )
    version = await firm.version(SPD)
    await words_upload(as_version(firm, version))
    paper, paper_version = uuid.uuid4(), uuid.uuid4()

    async def item(*_a: object) -> object:
        return SimpleNamespace(engagement_id=firm.engagement_id)

    async def paper_of(*_a: object) -> uuid.UUID:
        return paper

    async def latest(*_a: object) -> uuid.UUID:
        return paper_version

    monkeypatch.setattr(ebp_provisions, "assurance_item", item)
    monkeypatch.setattr(ebp_provisions, "paper_of_kind", paper_of)
    monkeypatch.setattr(ebp_provisions, "latest_version_id", latest)
    return SimpleNamespace(firm=firm, work_item=work_item, version=version)


async def _key(world: SimpleNamespace, quote: str) -> None:
    firm: Firm = world.firm
    await ebp_provisions.record_document_value(
        firm.person(),
        world.work_item,
        "entry_dates",
        "spd",
        value="Quarterly",
        evidence_version_id=world.version,
        page=2,
        quote=quote,
        note="The SPD (2025, p. 6) says entry is on the first day of each calendar quarter.",
        effective_on=None,
    )


@pytest.mark.asyncio
async def test_ac_a_keyed_spd_value_makes_the_conflict_live(world: SimpleNamespace) -> None:
    await _key(world, "the first day of each calendar quarter")
    docs, _ = await ebp_provisions._documents(  # pyright: ignore[reportPrivateUsage] -- the read under test
        world.firm.person().tenant, world.work_item
    )
    conflict, source, amended = ebp_provisions.compared(
        ENTRY,
        "First of month following",
        docs.get("entry_dates"),
        amendment_in_force=True,
        plan_year_end=None,
    )
    assert conflict == "SPD: Quarterly"
    assert source is not None
    assert (source.evidence_version_id, source.page) == (world.version, 2)
    assert source.match_id is not None  # the verified quote's region, for the viewer to light
    assert amended is None
    cited = await world.firm.seed.value(
        "SELECT count(*) FROM citations WHERE cited_from_type = 'ebp_provision' AND verified"
    )
    assert cited == 1


@pytest.mark.asyncio
async def test_ac_a_quote_not_on_the_page_keeps_nothing(world: SimpleNamespace) -> None:
    with pytest.raises(ebp_provisions.CitationUnverified):
        await _key(world, "the first day of each plan year")
    kept = await world.firm.seed.value(
        "SELECT count(*) FROM ebp_provisions WHERE work_item_id = $1", world.work_item
    )
    assert kept == 0


@pytest.mark.asyncio
async def test_an_amendment_value_needs_a_provision_it_governs_and_a_date(
    world: SimpleNamespace,
) -> None:
    firm: Firm = world.firm
    with pytest.raises(ebp_provisions.ReviewInvalid):
        await ebp_provisions.record_document_value(
            firm.person(),
            world.work_item,
            "entry_dates",
            "amendment",
            value="Quarterly",
            evidence_version_id=world.version,
            page=2,
            quote="the first day of each calendar quarter",
            note="Not an amendment provision.",
            effective_on=None,
        )
