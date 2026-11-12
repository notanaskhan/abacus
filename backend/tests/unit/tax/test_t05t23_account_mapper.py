"""T-05-T23 (TASK-7407; T-05 §6; DEC-4406): `tax.account_mapper` v1, without a model: the input
holds codes and names only (amounts redacted), code keeps a key only when it is published and
confident, every account is kept or abstained once, and the spec is wired (prompt, suite, tools,
`client_data: none`). The S37 suite's recorded outputs settle to their labels."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus.ai_gateway.prompts import registry
from abacus.modules.agents.api import spec_v2
from abacus.modules.tax.account_mapper import (
    CAPABILITY,
    PROPOSE_TOOL,
    MapAccountsInput,
    MapAccountsOutput,
    MappedAccount,
    model_input,
    redact_amounts,
    settle,
)

SUITE = Path(__file__).resolve().parents[4] / "evals" / "tax_account_mapper" / "suite.yaml"
KEYS = ["L1", "L21", "K 5", "8825 Rents"]


def _given(*accounts: tuple[str, str]) -> MapAccountsInput:
    return model_input(accounts, KEYS)


@pytest.mark.parametrize(
    ("name", "shown"),
    [
        ("Cash — operating", "Cash — operating"),
        ("Loan from partner $250,000", "Loan from partner [amount]"),
        ("Reserve 1,234,567.89", "Reserve [amount]"),
        ("Escrow (12,500)", "Escrow [amount]"),
        ("Deposit 1500.00", "Deposit [amount]"),
        ("Note 9876543", "Note [amount]"),
        ("Form 8825 rents 2025", "Form 8825 rents 2025"),  # a form, a year: not amounts
    ],
)
def test_names_never_carry_an_amount(name: str, shown: str) -> None:
    assert redact_amounts(name) == shown


def test_the_input_is_codes_and_names_only_unique_and_keys_sorted() -> None:
    given = _given(("1000", "Cash $5,000"), ("1000", "Cash again"), ("3000", "Partners' capital"))
    assert [a.code for a in given.accounts] == ["1000", "3000"]
    assert given.accounts[0].name == "Cash [amount]"
    assert given.published_keys == sorted(KEYS)
    dumped = given.model_dump()
    assert set(dumped) == {"accounts", "published_keys"}
    assert all(set(a) == {"code", "name"} for a in dumped["accounts"])
    with pytest.raises(ValueError):
        MapAccountsInput.model_validate(
            {"accounts": [{"code": "1", "name": "x", "amount": 5}], "published_keys": ["L1"]}
        )


def test_code_keeps_only_published_confident_single_answers() -> None:
    given = _given(
        ("1000", "Cash"),
        ("3000", "Capital"),
        ("4000", "Rents"),
        ("5000", "Mystery"),
        ("6000", "Twice"),
        ("7000", "Shy"),
        ("8000", "Wild"),
        ("9000", "Silent"),
    )
    answer = MapAccountsOutput(
        mappings=[
            MappedAccount(code="1000", key="L1", confidence=0.97),
            MappedAccount(code="3000", key="L21", confidence=0.9),
            MappedAccount(code="4000", key="L99", confidence=0.99),  # not published
            MappedAccount(code="5000", key=None, confidence=0.2),  # abstained
            MappedAccount(code="6000", key="L1", confidence=0.9),
            MappedAccount(code="6000", key="L21", confidence=0.9),  # answered twice
            MappedAccount(code="7000", key="K 5", confidence=0.3),  # under the minimum
            MappedAccount(code="8000", key="K 5", confidence=1.4),  # out of range
            MappedAccount(code="ghost", key="L1", confidence=0.9),  # not an account given
        ]
    )
    settled = settle(answer, given)
    assert [(m.code, m.key) for m in settled.kept] == [("1000", "L1"), ("3000", "L21")]
    assert dict(settled.abstained) == {
        "4000": "key_not_published",
        "5000": "abstained",
        "6000": "answered_twice",
        "7000": "low_confidence",
        "8000": "confidence_out_of_range",
        "9000": "no_answer",
    }
    assert len(settled.kept) + len(settled.abstained) == len(given.accounts)


def test_no_answer_abstains_on_every_account() -> None:
    given = _given(("1000", "Cash"), ("3000", "Capital"))
    settled = settle(None, given)
    assert settled.kept == () and [r for _, r in settled.abstained] == ["no_answer"] * 2


def test_the_spec_is_wired_and_runs_dark_for_client_data() -> None:
    spec = spec_v2(CAPABILITY)
    assert spec.prompt == "tax.map_accounts@v1" and spec.prompt in registry()
    assert spec.tier == "small" and spec.client_data == "none"
    assert spec.evaluation_suite == "evals/tax_account_mapper"
    assert "tri" in spec.data_classes
    assert PROPOSE_TOOL in str(spec.tools)
    assert f"tool.{PROPOSE_TOOL}@v1" in registry()


def test_the_suites_recorded_outputs_settle_to_their_labels() -> None:
    suite = cast(dict[str, Any], yaml.safe_load(SUITE.read_text(encoding="utf-8")))
    keys = list(suite["published_keys"])
    agreed = 0
    graded = 0
    for case in suite["cases"]:
        if case.get("category") != "pass":
            continue
        account = case["account"]
        given = model_input([(str(account["code"]), str(account["name"]))], keys)
        out = case["output"]
        answer = MapAccountsOutput(
            mappings=[
                MappedAccount(
                    code=str(account["code"]),
                    key=out.get("key"),
                    confidence=float(out.get("confidence", 0)),
                )
            ]
        )
        settled = settle(answer, given)
        label = case["label"].get("key")
        found = settled.kept[0].key if settled.kept else None
        graded += 1
        agreed += found == label
    assert graded >= 28
    assert agreed / graded >= suite["thresholds"]["top1_accuracy"]
