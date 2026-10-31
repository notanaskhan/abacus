"""AUD-31's consumer view of C9 v2 (A-03-T22; TASK-2507; SPEC-580 AC-18).

The fields AUD-31 reads on the mapping set, its rows, the picker and the mapped trial balance
exist with their names; Granite Peak FY2026 (AUD-31 f: 128 of 128, TB balanced 1 of 1, Prepared
· CD) fits the stub's models; BH FS groupings v1's import shape (three sheets and their headers)
and the picker's class order are pinned; the computed status words and A-09's reserved states are
the registry's; confirm and edit are human only and the adopt route is not mounted. A breaking
change to these shapes fails here.
"""

from __future__ import annotations

import json
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel._statuses import AccountMappingStateStatus, MappingSetStatus
from abacus.modules.assurance import tb_mapping_fixtures as fx
from abacus.modules.assurance.tb_mapping_contract import MappingRunOut, MappingSetSummaryOut
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.ledger.taxonomy_workbook import HEADERS

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
READS: dict[str, set[str]] = {
    "MappingSetSummaryOut": {
        "id",
        "trial_balance_id",
        "trial_balance_version_no",
        "entity_name",
        "period_end",
        "grouping_set_label",
        "run_status",
        "status",
        "tallies",
        "sign_offs",
        "content_hash",
    },
    "MappingTalliesOut": {"accounts", "mapped", "need_review", "tb_balanced", "tb_count"},
    "AccountMappingOut": {
        "account_code",
        "account_name",
        "balance",
        "fs_line_label",
        "grouping_label",
        "state",
        "method",
        "confidence",
        "was_fs_line_label",
        "edited_by_initials",
        "seen_version",
    },
    "MappingSetOut": {"summary", "rows", "subtotals", "allowed_actions"},
    "GroupingLinesOut": {"classes", "recently_used", "version_no"},
    "MappedTrialBalanceOut": {"lines", "debit", "credit", "content_hash", "unmapped"},
    "MappedFsLineOut": {"grouping_label", "fs_line_label", "debit", "credit", "net"},
}


@pytest.mark.parametrize("schema", sorted(READS))
def test_ac18_the_fields_aud31_reads_exist(schema: str) -> None:
    assert READS[schema] <= set(cast(Json, SCHEMAS[schema]["properties"])), schema


def test_ac18_granite_peak_128_fits() -> None:
    rows = fx.mapping_sets(fx.GRANITE_ENGAGEMENT)
    assert rows is not None
    summary = MappingSetSummaryOut.model_validate(rows[0])
    tallies = summary.tallies
    assert (tallies.accounts, tallies.mapped, tallies.need_review) == (128, 128, 0)
    assert (tallies.tb_balanced, tallies.tb_count) == (1, 1)
    assert summary.status == MappingSetStatus.PREPARED
    run = fx.run(fx.GRANITE_MAPPING)
    assert run is not None
    assert MappingRunOut.model_validate(run).run_done == 128


def test_ac18_the_bh_groupings_import_shape_is_pinned() -> None:
    assert HEADERS == {
        "Groupings": ("grouping_key", "grouping_label", "class"),
        "FS lines": ("fs_line_key", "fs_line_label", "grouping_key", "normal_balance"),
        "Number ranges": ("account_from", "account_to", "fs_line_key"),
    }
    picker = cast(Json, SCHEMAS["GroupingClassOut"]["properties"])
    classes = cast(list[str], cast(Json, picker["class"])["enum"])
    assert classes == ["assets", "liabilities", "equity", "revenue", "expenses"]


def test_ac18_the_status_words_and_the_reserved_states() -> None:
    assert {s.value for s in MappingSetStatus} == {
        "in_progress",
        "prepared",
        "reviewed",
        "changed_after_sign_off",
    }
    assert {"suggested", "adopted"} <= {s.value for s in AccountMappingStateStatus}


def test_ac18_confirm_and_edit_are_human_only_and_adopt_is_not_mounted() -> None:
    for action in ("mapping_set.confirm", "account_mapping.edit"):
        assert RULES[action].decisions.get("agent") == "deny"
        assert RULES[action].decisions.get("system", "deny") == "deny"
    assert not [p for p in PATHS if p.endswith("/adopt") and "mapping" in p]
