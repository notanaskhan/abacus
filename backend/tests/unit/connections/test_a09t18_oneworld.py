"""A-09-T18 (red): the OneWorld paths by code. A TB-by-subsidiary CSV splits into one balanced
trial balance per subsidiary; Pull all reads ten (five subsidiaries, two periods); an expired
token marks that subsidiary Needs reauth without retrying; nothing writes."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus.modules.connections import fake_oneworld as ow
from abacus.modules.connections.netsuite_split import SplitRefused, split

CSV = (
    b"Subsidiary,Account,Account Name,Debit,Credit\n"
    b'HP Distribution,1000,Cash,"1,400,000.00",\n'
    b'HP Distribution,3000,Capital,,"1,400,000.00"\n'
    b"HP Real Estate,1000,Cash,300000.00,\n"
    b"HP Real Estate,3000,Capital,,300000.00\n"
)


def test_a_tb_by_subsidiary_csv_splits_one_balanced_tb_per_subsidiary() -> None:
    parts = split(CSV)
    assert set(parts) == {"HP Distribution", "HP Real Estate"}
    assert parts["HP Distribution"][0].debit == D("1400000.00")


def test_an_unbalanced_subsidiary_or_missing_header_is_refused() -> None:
    with pytest.raises(SplitRefused):
        split(b"Subsidiary,Account,Account Name,Debit,Credit\nHP X,1,Cash,1.00,\n")
    with pytest.raises(SplitRefused):
        split(b"Account,Debit\n1,1\n")


def test_ac_pull_all_reads_ten_and_an_expired_token_is_needs_reauth_without_retry() -> None:
    assert list(ow.pull_all(ow.FakeOneWorld()).values()).count("snapshot") == 10
    calls: list[str] = []

    class Counting(ow.FakeOneWorld):
        def trial_balance(self, subsidiary: str, period: str) -> tuple[ow.FakeTbLine, ...]:
            calls.append(subsidiary)
            return super().trial_balance(subsidiary, period)

    out = ow.pull_all(Counting(expired=frozenset({"HP Distribution"})))
    assert out[("HP Distribution", "current")] == "needs_reauth"
    assert out[("HP Distribution", "prior")] == "needs_reauth"
    assert calls.count("HP Distribution") == 2  # once per period, never retried
    assert sum(v == "snapshot" for v in out.values()) == 8


def test_the_fake_connector_has_no_write_method() -> None:
    names = [n for n in dir(ow.FakeOneWorld) if not n.startswith("_")]
    assert not any(
        n.startswith(("write", "post", "put", "delete", "create", "update")) for n in names
    )
