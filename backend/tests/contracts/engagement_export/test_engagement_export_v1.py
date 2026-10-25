"""Engagement export v1 (A-01-T17; SPEC-344 AC-1 to AC-5; ADR-036 "a versioned schema with
tests"): the format's manifest and its generated JSON schema, the section slot, and the routes
stub behind `audits.binder_export` (404 off, 501 on until A-01-T18 and T22). Expectations come
from A-01 §3.6, §4.3 and §4.4. The Northwind example is Story 6.2's: 24 requests, 12 accepted
files (3 + 5 + 3 + 1)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from abacus.api.export_openapi import document
from abacus.kernel._flags import AUDITS_BINDER_EXPORT
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.evidence import export_contract, export_package
from abacus.modules.evidence.export_manifest import (
    FORMAT,
    FORMAT_VERSION,
    INDEX_COLUMNS,
    PROVENANCE_FILES,
    SCHEMA_ID,
    EngagementExportManifest,
    ManifestFile,
    archive_path_problem,
    manifest_json_schema,
)
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus_tools.codegen import export_manifest_schema

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
WI = "/v1/work-items/{work_item_id}/exports"

ROUTES: dict[tuple[str, str], str] = {
    ("post", WI): "export.create",
    ("get", WI): "export.read",
    ("get", "/v1/exports/{export_id}"): "export.read",
    ("post", "/v1/exports/{export_id}/undo"): "export.create",
    ("get", "/v1/exports/{export_id}/download"): "export.download",
}
ACTIONS = ("export.create", "export.read", "export.download")
CLIENT_ROLES = ("client_admin", "client_contributor")


# --- AC-1 the routes -----------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac1_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    responses = cast(Json, op["responses"])
    assert {"404", "501"} <= set(responses)


def test_ac1_create_takes_an_idempotency_key_and_answers_202() -> None:
    op = PATHS[WI]["post"]
    params = cast(list[Json], op.get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True
    assert "202" in cast(Json, op["responses"])


def test_ac1_download_is_resumable_and_answers_expired_and_not_ready() -> None:
    op = PATHS["/v1/exports/{export_id}/download"]["get"]
    params = cast(list[Json], op.get("parameters", []))
    assert any(p["name"] == "Range" and p["in"] == "header" for p in params)
    assert {"409", "410"} <= set(cast(Json, op["responses"]))


# --- AC-2 the shapes -----------------------------------------------------------------------------


def test_ac2_status_is_the_registry_enum() -> None:
    props = cast(dict[str, Json], SCHEMAS["EngagementExportOut"]["properties"])
    assert props["status"].get("$ref") == "#/components/schemas/EngagementExportStatus"
    statuses = cast(list[str], SCHEMAS["EngagementExportStatus"]["enum"])
    assert set(statuses) == {"queued", "packaging", "ready", "failed", "expired", "undone"}


@pytest.mark.parametrize(
    "model",
    [
        export_contract.ExportCreateIn,
        export_contract.ExportScopeIn,
        export_contract.EngagementExportOut,
        export_contract.EngagementExportPageOut,
        EngagementExportManifest,
    ],
)
def test_ac2_every_field_is_classified(model: type[BaseModel]) -> None:
    assert unclassified_fields(model) == []


def test_ac2_default_scope_is_accepted_files_with_the_audit_trail() -> None:
    body = export_contract.ExportCreateIn()
    assert (body.kind, body.scope.include_unaccepted, body.scope.include_audit_trail) == (
        "binder",
        False,
        True,
    )


# --- AC-3 who may export -------------------------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
def test_ac3_partner_and_manager_only_with_independence(action: str) -> None:
    rule = RULES[action]
    allowed = {r for r, d in rule.decisions.items() if d == "allow"}
    assert allowed == {"engagement_partner", "manager"}
    assert rule.independence


@pytest.mark.parametrize("action", ACTIONS)
def test_ac3_agent_system_and_clients_never_export(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system", *CLIENT_ROLES):
        assert decisions.get(principal, "deny") == "deny"


@pytest.mark.parametrize("action", ["export.create", "export.download"])
def test_ac3_create_and_download_need_fresh_mfa_and_onshore(action: str) -> None:
    rule = RULES[action]
    assert rule.mfa_recent and rule.not_offshore
    for support in ("platform_support", "platform_support_content"):  # SPEC-012: no cell at all
        assert rule.decisions.get(support, "deny") == "deny"


# --- AC-4 the flag -------------------------------------------------------------------------------


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )


async def test_ac4_flag_off_is_404_and_flag_on_is_501(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(export_contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await export_contract._stub(_ctx())  # pyright: ignore[reportPrivateUsage] -- the gate
    assert seen == [AUDITS_BINDER_EXPORT]
    monkeypatch.setattr(export_contract, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await export_contract._stub(_ctx())  # pyright: ignore[reportPrivateUsage] -- the gate


def test_ac4_the_flag_is_off_by_default() -> None:
    assert AUDITS_BINDER_EXPORT.default == "false"


# --- AC-5 the format: manifest v1 and its schema -------------------------------------------------


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _file(path: str, role: str, **extra: object) -> dict[str, object]:
    return {"path": path, "sha256": _sha(path), "bytes": 1024, "role": role, **extra}


BINDER = uuid.uuid4()
# Story 6.2's accepted files per category: 3 + 5 + 3 + 1.
FILES_PER_CATEGORY = {"01 Cash": 3, "02 Investments": 5, "03 Contributions": 3, "04 Payables": 1}


def northwind(**overrides: object) -> dict[str, object]:
    evidence: list[dict[str, object]] = []
    for category, n in FILES_PER_CATEGORY.items():
        for i in range(1, n + 1):
            evidence.append(
                _file(
                    f"evidence/{category}/{i:02d} Request {i}/v1__statement.pdf",
                    "evidence",
                    evidence={
                        "evidence_version_id": str(uuid.uuid4()),
                        "request_item_id": str(uuid.uuid4()),
                        "binder_id": str(BINDER),
                        "version_no": 1,
                        "review_state": "accepted",
                        "media_type": "application/pdf",
                    },
                )
            )
    files = [
        _file("README.txt", "readme"),
        _file("index.csv", "index"),
        _file("index.xlsx", "index"),
        _file("audit_trail/events.jsonl", "audit_trail"),
        *evidence,
        *(_file(p, "provenance") for p in PROVENANCE_FILES),
    ]
    manifest: dict[str, object] = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "export_id": str(uuid.uuid4()),
        "kind": "binder",
        "generated_at": datetime(2026, 9, 14, 14, 40, tzinfo=UTC).isoformat(),
        "as_of_seq": 48211,
        "tenant_id": str(uuid.uuid4()),
        "firm_name": "Brightwater Hale LLP",
        "client": {"client_id": str(uuid.uuid4()), "display_name": "Northwind Labs, Inc."},
        "engagement": {
            "engagement_id": str(uuid.uuid4()),
            "work_item_id": str(uuid.uuid4()),
            "display_name": "Northwind FY2026 audit",
            "period_end": date(2026, 6, 30).isoformat(),
        },
        "requested_by": {"user_id": str(uuid.uuid4()), "display_name": "Hannah Leclerc"},
        "requested_at": datetime(2026, 9, 14, 14, 39, 50, tzinfo=UTC).isoformat(),
        "scope": {
            "binder_ids": [str(BINDER)],
            "include_unaccepted": False,
            "include_audit_trail": True,
        },
        "counts": {"request_count": 24, "file_count": 12, "requests_without_file": 12},
        "index_columns": list(INDEX_COLUMNS),
        "sections": [],
        "files": sorted(files, key=lambda f: str(f["path"])),
    }
    return {**manifest, **overrides}


def test_ac5_the_northwind_example_is_a_valid_v1_manifest() -> None:
    m = EngagementExportManifest.model_validate(northwind())
    assert (m.format, m.format_version) == ("accrued.binder-export", "1.0")
    assert (m.counts.request_count, m.counts.file_count) == (24, 12)
    assert sum(1 for f in m.files if f.role == "evidence") == 12
    again = EngagementExportManifest.model_validate_json(m.model_dump_json())
    assert again == m


def test_ac5_the_committed_schema_is_the_generated_one() -> None:
    target = export_manifest_schema.TARGET
    assert target.read_text(encoding="utf-8") == export_manifest_schema.render()
    assert export_manifest_schema.main(["--check"]) == 0


def test_ac5_the_schema_is_versioned_and_closed() -> None:
    schema = manifest_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == SCHEMA_ID
    props = cast(dict[str, Json], schema["properties"])
    assert props["format"]["const"] == "accrued.binder-export"
    assert props["format_version"]["const"] == "1.0"
    assert schema["additionalProperties"] is False
    for definition in cast(dict[str, Json], schema["$defs"]).values():
        if definition.get("type") == "object":
            assert definition["additionalProperties"] is False
    assert set(cast(list[str], schema["required"])) >= {
        "format",
        "format_version",
        "export_id",
        "generated_at",
        "as_of_seq",
        "files",
        "counts",
        "index_columns",
    }


def test_ac5_another_format_version_is_not_v1() -> None:
    with pytest.raises(ValidationError):
        EngagementExportManifest.model_validate(northwind(format_version="1.1"))
    with pytest.raises(ValidationError):
        EngagementExportManifest.model_validate(northwind(unknown_field=True))


@pytest.mark.parametrize(
    "path",
    [
        "../../etc/passwd",
        "/evidence/a.pdf",
        "evidence/./a.pdf",
        "evidence//a.pdf",
        "evidence\\a.pdf",
        "C:/evidence/a.pdf",
        "evidence/a\u0000.pdf",
        "evidence/a\u202e.pdf",  # right-to-left override
        "evidence/cafe\u0301.pdf",  # not NFC
        "evidence/" + "x" * 180,
    ],
)
def test_ac5_unsafe_archive_paths_never_reach_a_manifest(path: str) -> None:
    assert archive_path_problem(path) is not None
    with pytest.raises(ValidationError):
        ManifestFile.model_validate(
            {"path": path, "sha256": "0" * 64, "bytes": 1, "role": "readme"}
        )


def test_ac5_a_formula_like_file_name_is_a_safe_path() -> None:
    """Cells are neutralised by the index writer; the archive path itself is literal (A-01 6.2)."""
    assert archive_path_problem('evidence/01 Cash/01 Bank/v1__=HYPERLINK("x","y").pdf') is None


def test_ac5_unaccepted_files_need_the_option() -> None:
    m = northwind()
    files = cast(list[dict[str, object]], m["files"])
    first = next(f for f in files if f["role"] == "evidence")
    first["evidence"] = {
        **cast(dict[str, object], first["evidence"]),
        "review_state": "needs_review",
    }
    with pytest.raises(ValidationError, match="include_unaccepted"):
        EngagementExportManifest.model_validate(m)
    scope = {**cast(dict[str, object], m["scope"]), "include_unaccepted": True}
    assert EngagementExportManifest.model_validate({**m, "scope": scope})


Files = list[dict[str, object]]


def _reversed(files: Files) -> Files:
    return list(reversed(files))


def _self_listed(files: Files) -> Files:
    return [*files, _file("manifest.json", "readme")]


def _one_evidence_file_short(files: Files) -> Files:
    evidence = [f for f in files if f["role"] == "evidence"]
    return [f for f in files if f is not evidence[-1]]


@pytest.mark.parametrize(
    ("change", "problem"),
    [(_reversed, "sorted"), (_self_listed, "role"), (_one_evidence_file_short, "file_count")],
)
def test_ac5_the_manifest_is_consistent(change: Callable[[Files], Files], problem: str) -> None:
    m = northwind()
    files = change(cast(list[dict[str, object]], m["files"]))
    with pytest.raises(ValidationError, match=problem):
        EngagementExportManifest.model_validate({**m, "files": files})


def test_ac5_the_index_columns_are_format_1_0s() -> None:
    with pytest.raises(ValidationError, match="index_columns"):
        EngagementExportManifest.model_validate(northwind(index_columns=["request"]))


# --- the section slot (SPEC-344 §6) --------------------------------------------------------------


async def _provider(
    _tenant: TenantContext, _request: export_package.SectionRequest
) -> list[export_package.SectionFile]:
    return []


def test_ac5_sections_register_once_under_a_safe_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(export_package, "_SECTIONS", {})
    assert export_package.missing_core_sections() == (
        "citations",
        "fulfilments",
        "index",
        "review_decisions",
        "screening",
    )
    export_package.register_export_section("screening", _provider)
    export_package.register_export_section("materiality", _provider, section_version="1.1")
    with pytest.raises(export_package.ExportSectionInvalid):
        export_package.register_export_section("screening", _provider)
    for bad in ("audit_trail", "manifest", "Bad", "x", "../x"):
        with pytest.raises(export_package.ExportSectionInvalid):
            export_package.register_export_section(bad, _provider)
    assert [s.name for s in export_package.registered_sections()] == ["materiality", "screening"]
    assert "screening" not in export_package.missing_core_sections()
    assert export_package.section_path("screening", "x.csv") == "provenance/screening.csv"
    assert export_package.section_path("index", "x.csv") == "index.csv"
    assert export_package.section_path("materiality", "m.csv") == "sections/materiality/m.csv"
    with pytest.raises(export_package.ExportSectionInvalid):
        export_package.section_path("materiality", "../m.csv")
