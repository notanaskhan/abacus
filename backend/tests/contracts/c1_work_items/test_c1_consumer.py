"""C1 v1 consumer tests (F-03-T19; F-02-T11): the work-item and engagement-lifecycle shapes
consumers rely on. Schema shape only."""

from __future__ import annotations

import json
from typing import cast

from abacus.api.export_openapi import document
from abacus.modules.engagements.gate_policy import required_gates

SCHEMAS = cast(dict[str, dict[str, object]], json.loads(document())["components"]["schemas"])
EXCLUDED = {"audit", "single_audit", "yellow_book", "pcaob_audit", "esg", "forensics"}


def _enum(model: str, field: str) -> list[str]:
    props = cast(dict[str, dict[str, object]], SCHEMAS[model]["properties"])
    return cast(list[str], props[field]["enum"])


def test_c1_the_engagement_type_holds_the_14_types_and_no_excluded_one() -> None:
    types = set(_enum("EngagementSummaryOut", "type"))
    assert len(types) == 14 and not types & EXCLUDED


def test_c1_status_is_the_registry_lifecycle() -> None:
    props = cast(dict[str, dict[str, object]], SCHEMAS["EngagementSummaryOut"]["properties"])
    assert props["status"]["$ref"] == "#/components/schemas/EngagementStatus"
    assert len(cast(list[str], SCHEMAS["EngagementStatus"]["enum"])) == 8


def test_c1_the_projection_carries_service_line_and_g1_to_g3_gate_facts() -> None:
    assert set(_enum("EngagementSummaryOut", "service_line")) == {
        "audit",
        "tax",
        "cas",
        "advisory",
    }
    assert set(_enum("GateOut", "gate")) == {"G1", "G2", "G3"}
    props = cast(dict[str, object], SCHEMAS["GateOut"]["properties"])
    assert {"gate", "met", "blockers"} <= set(props)


def test_c1_work_items_have_the_five_kinds() -> None:
    assert set(_enum("WorkItemOut", "kind")) == {
        "assurance",
        "tax_return",
        "close",
        "notice",
        "advisory_project",
    }


def test_c1_per_type_gate_policy_for_g1_to_g3() -> None:
    def c1(engagement_type: str) -> list[str]:
        return [g for g in required_gates(engagement_type) if g in ("G1", "G2", "G3")]

    assert c1("ebp_audit") == ["G1", "G2", "G3"]  # attest: all three
    assert c1("cas_monthly_close") == ["G1", "G3"]  # non-attest CAS: no G2
    assert c1("notice_response") == ["G3"]
