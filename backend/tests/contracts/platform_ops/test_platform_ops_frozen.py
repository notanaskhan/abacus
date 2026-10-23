"""Platform-ops contract v1, frozen by Q-01-T57 (`docs/contracts/platform-ops.md` section 10).

The contract has no OpenAPI models for `abacus_tools.contracts` to snapshot, so the parts already
live behind it are pinned here: the runtime-config keys (section 3.2, and the TypeScript mirror),
the public routes and readiness check names (section 3.3), the provisioning workflow's v1 shapes
(section 3.6) and the SES identity port (section 3.8). A breaking change to any of them is v2 with
an overlap (section 10), not an edit that turns this file red.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

from abacus.api.public_routes import PUBLIC_ROUTES, READINESS_CHECKS
from abacus.modules.communications.api import SesIdentityPort
from abacus.modules.platform.api import ProvisionTenantInput, ProvisionTenantResult

REPO = Path(__file__).resolve().parents[4]
CONTRACT = REPO / "docs" / "contracts" / "platform-ops.md"
RUNTIME_CONFIG_TS = REPO / "apps" / "web" / "src" / "app-core" / "runtime-config.ts"
V1_RUNTIME_KEYS = {"environment", "oidc", "sentry", "release", "portal_base_domain"}


def _contract() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_the_contract_is_recorded_frozen_at_v1() -> None:
    assert "| Status | frozen v1 (Q-01-T57" in _contract()


def test_section_3_2_runtime_config_keys_are_the_v1_keys() -> None:
    section = _contract().split("### 3.2", 1)[1].split("### 3.3", 1)[0]
    example = re.search(r"```json\n(.*?)\n```", section, re.S)
    assert example
    assert set(json.loads(example.group(1))) == V1_RUNTIME_KEYS
    mirror = RUNTIME_CONFIG_TS.read_text(encoding="utf-8")
    interface = re.search(r"export interface RuntimeConfig \{(.*?)\n\}", mirror, re.S)
    assert interface
    assert set(re.findall(r"^\s+(\w+)\??:", interface.group(1), re.M)) == V1_RUNTIME_KEYS


def test_section_3_3_probes_and_readiness_check_names() -> None:
    assert {"/healthz", "/readyz"} <= set(PUBLIC_ROUTES)
    assert tuple(name for name, _ in READINESS_CHECKS) == (
        "database",
        "identity_database",
        "temporal",
        "scanner",
        "platform_key",
    )


def test_section_3_6_provisioning_shapes_keep_their_v1_fields() -> None:
    assert [f.name for f in dataclasses.fields(ProvisionTenantInput)] == [
        "tenant_id",
        "slug",
        "synthetic",
        "plan",
        "admins",
        "idempotency_key",
        "operator",
    ]
    assert [f.name for f in dataclasses.fields(ProvisionTenantResult)] == [
        "tenant_id",
        "key_status",
        "entitlement_rows",
        "invitations_sent",
    ]


def test_section_3_8_the_ses_identity_port_keeps_its_three_methods() -> None:
    methods = {
        name
        for name in vars(SesIdentityPort)
        if not name.startswith("_") and callable(getattr(SesIdentityPort, name))
    }
    assert methods == {"create_identity", "identity_status", "delete_identity"}
