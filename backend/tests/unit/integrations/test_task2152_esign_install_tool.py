"""TASK-2152 (ADR-342; DEC-1279): the operator command for a firm's DocuSeal install, without a
database. The key comes only from the task's environment, is checked against DocuSeal before
anything is written, and never reaches the output; the catalogue document is the hidden
e-signature row; the commands are allowlisted for ops requests.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from abacus.modules.integrations.api import registered_keys
from abacus_tools import esign_install as tool
from abacus_tools import integration_catalog
from abacus_tools.release import OPS_COMMANDS

pytestmark = pytest.mark.asyncio
KEY = "synthetic0key0not0a0secret0abcdef"


async def test_the_key_comes_only_from_the_environment_and_is_shape_checked() -> None:
    assert tool.api_key({tool.KEY_ENV: f"  {KEY}\n"}) == KEY
    with pytest.raises(tool.Refused, match="not set"):
        tool.api_key({})
    with pytest.raises(tool.Refused, match="does not look like"):
        tool.api_key({tool.KEY_ENV: "short"})
    with pytest.raises(tool.Refused) as refused:
        tool.api_key({tool.KEY_ENV: "x" * 10 + " " + "y" * 20})
    assert "y" * 20 not in str(refused.value)  # a refusal never echoes the key


async def test_the_sealed_secret_is_the_account_json_the_adapter_opens() -> None:
    from abacus.modules.signatures.docuseal import DocuSealAccount

    account = DocuSealAccount.from_secret(tool.secret_of(KEY))
    assert account == DocuSealAccount(KEY, "api.docuseal.com")


async def test_docuseal_refusing_the_key_is_a_refusal_and_the_key_goes_only_to_its_host() -> None:
    seen: list[httpx.Request] = []

    def docuseal(status: int) -> httpx.MockTransport:
        def answer(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(status, json={"id": 1})

        return httpx.MockTransport(answer)

    await tool.check_key(KEY, docuseal(200))
    with pytest.raises(tool.Refused, match="refused the key"):
        await tool.check_key(KEY, docuseal(401))
    with pytest.raises(tool.Refused, match="answered 500"):
        await tool.check_key(KEY, docuseal(500))
    assert {(r.url.host, r.url.path) for r in seen} == {("api.docuseal.com", "/user")}
    assert all(r.headers["X-Auth-Token"] == KEY for r in seen)


async def test_a_refused_key_writes_nothing() -> None:
    def refuse(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    # Unreachable database URLs: a refusal must come before any connection is opened.
    with pytest.raises(tool.Refused, match="refused the key"):
        await tool.run(
            "connect",
            tenant_id=uuid.uuid4(),
            operator="probe-op",
            requested_by=uuid.uuid4(),
            app_dsn="postgresql+asyncpg://nobody@127.0.0.1:9/none",
            ops_dsn="postgresql://nobody@127.0.0.1:9/none",
            environ={tool.KEY_ENV: KEY},
            transport=httpx.MockTransport(refuse),
        )


async def test_operator_and_requester_are_required_before_any_write() -> None:
    app = "postgresql+asyncpg://nobody@127.0.0.1:9/none"
    ops = "postgresql://nobody@127.0.0.1:9/none"
    environ = {tool.KEY_ENV: KEY}
    with pytest.raises(tool.Refused, match="lower-case handle"):
        await tool.run(
            "connect",
            tenant_id=uuid.uuid4(),
            operator="a@b.example",
            requested_by=uuid.uuid4(),
            app_dsn=app,
            ops_dsn=ops,
            environ=environ,
        )
    with pytest.raises(tool.Refused, match="requested-by"):
        await tool.run(
            "connect",
            tenant_id=uuid.uuid4(),
            operator="probe-op",
            requested_by=None,
            app_dsn=app,
            ops_dsn=ops,
            environ=environ,
        )


async def test_the_catalogue_document_is_the_hidden_esignature_row() -> None:
    document = integration_catalog.read_document(tool.DOCUMENT)
    (row,) = document.rows
    assert (row.key, row.category, row.adapter_key) == ("docuseal", "esignature", "docuseal")
    assert row.listing_status == "hidden" and row.surfaces == ["workbench"]
    assert row.ownership_mode == "firm" and row.connector_provider is None
    assert "docuseal" not in registered_keys()  # never a read adapter, so never a portal card
    assert json.dumps(row.as_row())  # the load's JSON


async def test_the_commands_are_allowlisted_for_ops_requests() -> None:
    for sub in ("connect", "rotate", "disconnect", "status"):
        assert f"abacus_tools.esign_install {sub}" in OPS_COMMANDS
