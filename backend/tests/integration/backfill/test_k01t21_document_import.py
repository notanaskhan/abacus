"""K-01-T21 (TASK-2808; K-01 §4.4, AC7.7; DEC-1856): "The seeded EBP v3 PDF imports as 67 steps
with 3 flags, every quote verified on its page, and a firm the importer may not read gets 409."

Hannah (a firm admin, `methodology.manage`) uploads the synthetic EBP v3 PDF and starts the
import. The start is recorded by a stand-in for the Temporal client; the workflow's activities
then run in this process in its order (extract, each batch with the previous batch's run, finish).
The model is a scripted stand-in on the `bedrock` route that answers with the importer's fake
parser, so the gateway's boundary, budget and usage steps run unchanged. Never a real model.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final, cast

import httpx
import pytest
from temporalio.client import Client
from types_boto3_s3 import S3Client

from abacus.ai_gateway import ModelRequest, ModelResponse
from abacus.ai_gateway.boundary import clear_cache
from abacus.ai_gateway.routes import configure_route
from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.scanning import forget_injected
from abacus.kernel.storage import s3_client
from abacus.kernel.temporal import configure_temporal_client
from abacus.modules.agents import methodology_import as mi
from abacus.modules.agents.workflow_types import (
    ImportBatchInput,
    ImportFinishInput,
    MethodologyImportInput,
)
from abacus.modules.evidence import storage
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import (
    DANGLING_STEP,
    SPLIT_STEP,
    UNSURE_STEP,
    ebp_v3_document_pdf,
)

from .q03_agent_support import Starts
from .support import Json, Net, Person
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's flag seeding
)

pytestmark = pytest.mark.asyncio

BUCKET: Final = "backfill-k01t21-importer"
MASTER: Final = b"backfill-k01t21-importer-master-key-01234"
FLAGS: Final = (
    "methodology.programs",
    "methodology.lifecycle",
    "methodology.import_review",
    "methodology.importer",
)
TEMPLATE: Final = "BH Audit Methodology · EBP"


@dataclass
class Model:
    """The importer's fake parser on the `bedrock` route; records every request."""

    seen: list[ModelRequest] = field(default_factory=list[ModelRequest])

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.seen.append(request)
        return ModelResponse(mi.fake_parse(request), 900, 600, request.model)


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
    forget_injected()
    yield
    forget_injected()
    storage.reset_storage()
    reset_key_service()


@pytest.fixture(autouse=True)
def starts() -> Iterator[Starts]:
    made = Starts()
    configure_temporal_client(cast(Client, made))
    yield made
    configure_temporal_client(None)


@pytest.fixture(autouse=True)
def model(engines: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[Model]:
    today = system_now().date().isoformat()
    catalog = {
        tier: {
            "name": f"stub-{tier}",
            "ids": {"bedrock": f"claude-stub{tier}-0-0"},
            "usd_in": i,
            "usd_out": o,
        }
        for tier, i, o in (
            ("small", "0.80", "4.00"),
            ("medium", "3.00", "15.00"),
            ("large", "15.00", "75.00"),
        )
    }
    monkeypatch.setenv("ABACUS_ALLOW_REAL_MODEL_LOCALLY", "true")  # synthetic firms only
    monkeypatch.setenv("ABACUS_MODEL_ROUTES", json.dumps(["bedrock"]))
    monkeypatch.setenv(
        "ABACUS_ROUTE_PARITY",
        json.dumps({"bedrock": {"checked_on": today, "report_sha256": "0" * 64}}),
    )
    monkeypatch.setenv("ABACUS_MODEL_CATALOG", json.dumps(catalog))
    limits = {f"claude-stub{tier}-0-0": {"rpm": 600, "tpm": 1_000_000} for tier in catalog}
    monkeypatch.setenv("ABACUS_PROVIDER_LIMITS", json.dumps(limits))
    settings.cache_clear()
    clear_cache()
    stand_in = Model()
    configure_route("bedrock", stand_in)
    yield stand_in
    configure_route("bedrock", None)
    clear_cache()
    settings.cache_clear()


async def _firm(net: Net, *, synthetic: bool = True) -> tuple[uuid.UUID, Person]:
    tenant = await net.seed.firm()
    hannah = await net.seed.person(tenant, "firm_admin")
    await net.seed.run("UPDATE firms SET synthetic = $2 WHERE tenant_id = $1", tenant, synthetic)
    await _flags(net, tenant, *FLAGS)
    return tenant, hannah


async def _uploaded(net: Net, hannah: Person) -> str:
    made = await net.http.post(
        "/v1/methodology/imports",
        json={"template_name": TEMPLATE, "engagement_types": ["ebp_audit"]},
        headers={**net.headers(hannah), "Idempotency-Key": f"k01t21-{uuid.uuid4()}"},
    )
    assert made.status_code == 201, made.text
    import_id = cast(str, cast(Json, made.json())["id"])
    put = await net.http.put(
        f"/v1/methodology/imports/{import_id}/files/document_pdf?filename=BH EBP v3.pdf",
        content=ebp_v3_document_pdf(),
        headers={**net.headers(hannah), "Content-Type": "application/octet-stream"},
    )
    assert put.status_code == 200, put.text
    return import_id


async def _start(net: Net, hannah: Person, import_id: str) -> httpx.Response:
    return await net.call("POST", f"/v1/methodology/imports/{import_id}/start", hannah)


async def _run_workflow(tenant: uuid.UUID, hannah: Person, import_id: str) -> str:
    """The workflow's activities in its order: extract, each batch, finish."""
    given = MethodologyImportInput(str(tenant), import_id, str(hannah.user_id))
    pages = await mi.extract_pages(given)
    assert not pages.held
    run_ids: list[str] = []
    for first, last in mi.batches(pages.page_count):
        outcome = await mi.parse_batch(
            ImportBatchInput(
                str(tenant),
                import_id,
                str(hannah.user_id),
                first,
                last,
                run_ids[-1] if run_ids else None,
            )
        )
        assert not outcome.stop
        assert outcome.run_id is not None
        run_ids.append(outcome.run_id)
    return await mi.finish(ImportFinishInput(str(tenant), import_id, run_ids))


async def test_ac_the_seeded_pdf_imports_as_67_steps_with_3_flags_all_verified(
    net: Net, starts: Starts, model: Model
) -> None:
    tenant, hannah = await _firm(net)
    import_id = await _uploaded(net, hannah)
    started = await _start(net, hannah, import_id)
    assert started.status_code == 200, started.text
    assert cast(Json, started.json())["status"] == "parsing"
    assert [c.id for c in starts.calls] == [mi.workflow_id(tenant, uuid.UUID(import_id))]

    assert await _run_workflow(tenant, hannah, import_id) == "needs_review"
    # Every page reached the model only inside the one untrusted document block.
    assert model.seen
    assert all(r.user.count(mi.UNTRUSTED_DOCUMENT) == 1 for r in model.seen)

    view = cast(
        Json, (await net.call("GET", f"/v1/methodology/imports/{import_id}", hannah)).json()
    )
    assert view["status"] == "needs_review"
    version = uuid.UUID(cast(str, view["version_id"]))
    steps = await net.seed.rows(
        "SELECT p.code, s.number, s.parse_flag, s.origin, s.mandatory, src.verified "
        "FROM program_steps s JOIN programs p ON p.id = s.program_id "
        "JOIN program_step_sources src ON src.step_id = s.id WHERE s.version_id = $1",
        version,
    )
    assert len(steps) == 67
    assert all(r["verified"] for r in steps)
    # The importer proposes only: nothing it wrote is mandatory, and every step is its own.
    assert {(r["origin"], r["mandatory"]) for r in steps} == {("importer", False)}
    assert {(r["code"], r["number"]): r["parse_flag"] for r in steps if r["parse_flag"]} == {
        (f"BH-EBP-{SPLIT_STEP[0]}", SPLIT_STEP[1]): "split_across_pages",
        (f"BH-EBP-{UNSURE_STEP[0]}", UNSURE_STEP[1]): "low_confidence",
        (f"BH-EBP-{DANGLING_STEP[0]}", DANGLING_STEP[1]): "cross_reference_missing",
    }

    # The KNW-02 viewer reads a stored page and its words (K-01-T20's routes).
    file_id = (
        await net.seed.rows(
            "SELECT id FROM methodology_source_files WHERE import_id = $1", uuid.UUID(import_id)
        )
    )[0]["id"]
    base = f"/v1/methodology/versions/{version}/files/{file_id}/pages/2"
    png = await net.call("GET", base, hannah)
    assert png.status_code == 200, png.text
    assert png.headers["content-type"] == "image/png"
    assert png.headers["cache-control"] == "no-store"
    words = await net.call("GET", f"{base}/words", hannah)
    assert words.status_code == 200, words.text
    assert cast(Json, words.json())["page_count"] == 9

    # Finish runs once: a replayed finish finds the import no longer parsing.
    again = await mi.parse_batch(
        ImportBatchInput(str(tenant), import_id, str(hannah.user_id), 1, 8)
    )
    assert again.stop


async def test_ac7_7_a_firm_the_importer_may_not_read_gets_409_and_no_model_call(
    net: Net, starts: Starts, model: Model
) -> None:
    _, hannah = await _firm(net, synthetic=False)
    import_id = await _uploaded(net, hannah)
    refused = await _start(net, hannah, import_id)
    assert (refused.status_code, refused.json()["detail"]) == (409, "importer_not_enabled")
    assert starts.calls == []
    assert model.seen == []


async def test_ac7_7_the_importer_flag_off_gets_409(net: Net, starts: Starts) -> None:
    tenant, hannah = await _firm(net)
    await net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        tenant,
        "methodology.importer",
    )
    forget_flags()
    import_id = await _uploaded(net, hannah)
    refused = await _start(net, hannah, import_id)
    assert (refused.status_code, refused.json()["detail"]) == (409, "importer_not_enabled")
    assert starts.calls == []
