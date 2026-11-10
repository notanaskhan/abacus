"""R-02-T03 (TASK-5103; SPEC-646 AC-1, AC-2, AC-5, AC-7): C18's stub. An unregistered kind fails
closed with 409; every decide route has its one action, denied to agent and system with a fresh
second factor; the decider rule follows OQ-1; no DTO carries a field the pack rule bans."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.modules.engagements.api import (
    CLIENT_APPROVAL_KINDS,
    DECIDER_RULES,
    ApprovalKindNotRegistered,
    client_approval_provider,
)
from abacus.modules.portal import approvals_contract

REPO = Path(__file__).resolve().parents[4]
BASE = "/v1/portal/approvals"
DECIDE = {
    f"{BASE}/proposed-entries/{{entry_id}}/decide": "proposed_entry.client_decide",
    f"{BASE}/uncorrected-misstatements/{{item_id}}/acknowledge": (
        "uncorrected_misstatements.acknowledge"
    ),
    f"{BASE}/packages/{{package_id}}/decide": "close_package.client_decide",
}
BANNED = re.compile(
    r"materiality|threshold|policy|review_note|sign_off|signoff|agent|confidence|internal_status",
    re.I,
)


def _doc() -> dict[str, object]:
    return cast(dict[str, object], json.loads(document()))


# R-02-T11 (DEC-3009): adjustments registers `proposed_entry` and reporting `fs_draft`; the
# other two kinds still fail closed until R-02-T15 (assurance) and C-02 or A-08 register them.
# R-02-T15 (S33) registered `uncorrected_misstatements`; `fs_package` waits for C-02 or A-08.
UNREGISTERED = ("fs_package",)
REGISTERED = ("proposed_entry", "fs_draft", "uncorrected_misstatements")


def test_unregistered_kind_fails_closed() -> None:
    import abacus.api.app  # noqa: F401  # pyright: ignore[reportUnusedImport] -- every module's registrations

    for kind in UNREGISTERED:
        with pytest.raises(ApprovalKindNotRegistered):
            client_approval_provider(kind)
    with pytest.raises(ApprovalKindNotRegistered):
        client_approval_provider("made_up_kind")
    assert set(REGISTERED) <= set(CLIENT_APPROVAL_KINDS)
    for kind in REGISTERED:
        client_approval_provider(kind)


async def test_package_decide_is_409_until_a_provider_registers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # R-02-T14 (DEC-3112): the route checks `portal.approvals` first; with it on, the kind's slot
    # answers 409 before any service call.
    async def on(*_a: object) -> bool:
        return True

    monkeypatch.setattr(approvals_contract, "flag_enabled", on)
    with pytest.raises(ApprovalKindNotRegistered):
        await approvals_contract.decide_package_route(
            uuid4(),
            approvals_contract.PackageDecideIn(decision="approve", seen_hash="h"),
            cast("approvals_contract.AuthContext", SimpleNamespace(tenant=None)),
            "key",
        )


@pytest.mark.parametrize("path", sorted(DECIDE))
def test_decide_routes_are_live_with_one_action(path: str) -> None:
    """R-02-T11: the decide routes answer through C18's service (409 for a stale item or an
    unregistered kind), no longer 501."""
    paths = cast(dict[str, dict[str, dict[str, object]]], _doc()["paths"])
    assert list(paths[path]) == ["post"]
    responses = cast(dict[str, object], paths[path]["post"]["responses"])
    assert "501" not in responses and "409" in responses


@pytest.mark.parametrize("action", sorted(set(DECIDE.values())))
def test_decisions_are_human_with_a_fresh_second_factor(action: str) -> None:
    matrix = yaml.safe_load((REPO / "docs/architecture/permission-matrix/portal.yaml").read_text())
    row = matrix["actions"][action]
    assert (row["agent"], row["system"]) == ("deny", "deny")
    assert row["scope_only"] == "required"
    assert row["mfa_recent"] == "required"
    assert not {"firm_admin", "engagement_partner", "manager", "client_service"} & set(row)


def test_decider_rule_follows_oq_1() -> None:
    assert set(DECIDER_RULES) == CLIENT_APPROVAL_KINDS
    for kind in ("proposed_entry", "uncorrected_misstatements", "fs_draft"):
        assert DECIDER_RULES[kind].any_of == {"owner", "approver_of_record"}
        assert not DECIDER_RULES[kind].attest_also
    assert DECIDER_RULES["fs_package"].attest_also == {"ske_designee"}


def test_no_approval_dto_carries_a_banned_field() -> None:
    doc = _doc()
    schemas = cast(dict[str, dict[str, dict[str, object]]], doc["components"])["schemas"]
    paths = cast(dict[str, object], doc["paths"])
    used: set[str] = set()
    for path, item in paths.items():
        if path.startswith(BASE):
            used |= set(re.findall(r"#/components/schemas/(\w+)", json.dumps(item)))
    assert "ApprovalItemDetailOut" in used
    for name in used:
        for field in cast(dict[str, object], schemas[name].get("properties", {})):
            assert not BANNED.search(field), f"{name}.{field}"
