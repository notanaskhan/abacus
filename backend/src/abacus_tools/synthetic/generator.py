"""`generate` — the synthetic client entry point (SPEC-001 §6)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, localcontext
from random import Random
from typing import Literal

from abacus_tools.synthetic import adversarial as _adversarial
from abacus_tools.synthetic import flaws as _flaws
from abacus_tools.synthetic import names
from abacus_tools.synthetic.artefacts import aging, bank_statements, trial_balances
from abacus_tools.synthetic.ledger import ACCOUNTS, Books, build_books
from abacus_tools.synthetic.model import (
    AdversarialPayload,
    ClientEntity,
    Flaw,
    Manifest,
    SyntheticClient,
)
from abacus_tools.synthetic.requests import request_list
from abacus_tools.synthetic.rng import stream

# Bump whenever output changes for any input; the golden test fails until its hash is updated.
GENERATOR_VERSION = "1.2.0"


def _entity(
    seed: int, prefix: str, name: str, start: date, months: int, size: str
) -> tuple[ClientEntity, Books]:
    books = build_books(seed, prefix, start, months, size)
    entity = ClientEntity(
        name=name,
        ein=names.ein(stream(seed, f"{prefix}:ein")),
        currency="USD",
        period_start=books.period_start,
        period_end=books.period_end,
        accounts=ACCOUNTS,
        journal_entries=books.entries,
        trial_balances=trial_balances(books.entries, books.month_ends, name),
        bank_accounts=books.bank_accounts,
        bank_statements=bank_statements(books),
        ar_aging=aging("ar", books.receivables, books.period_end),
        ap_aging=aging("ap", books.payables, books.period_end),
    )
    return entity, books


def generate(
    seed: int,
    *,
    entities: int = 1,
    months: int = 12,
    start: date = date(2025, 1, 1),
    size: Literal["small"] = "small",
    flaws: Sequence[str] = (),
    adversarial: bool = False,
) -> SyntheticClient:
    # Pin decimal arithmetic so a caller's context (precision, rounding) can't change the output.
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        return _generate(seed, entities, months, start, size, flaws, adversarial)


def _generate(
    seed: int,
    entities: int,
    months: int,
    start: date,
    size: str,
    flaws: Sequence[str],
    adversarial: bool,
) -> SyntheticClient:
    if not 1 <= entities <= 5:
        raise ValueError(f"entities must be between 1 and 5, got {entities}")
    if not 1 <= months <= 36:
        raise ValueError(f"months must be between 1 and 36, got {months}")
    if size != "small":
        raise ValueError(f"unknown size {size!r}; valid: small")
    requested = _flaws.parse(flaws)
    if months == 1 and any(
        f.category == "stale" and f.artefact == "trial_balance" for f in requested
    ):
        raise ValueError(
            "flaw 'stale' on 'trial_balance' needs months >= 2 (no earlier month end)"
        )
    base = names.client_base(stream(seed, "client"))
    built = [
        _entity(seed, f"entity{i}", names.entity_name(base, i), start, months, size)
        for i in range(entities)
    ]
    first, books = built[0]
    requests = request_list()
    flaw_records: tuple[Flaw, ...] = ()
    if requested:

        def decoy() -> ClientEntity:
            other = names.client_base(stream(seed, "decoy:name"))
            if other == base:
                other = f"{other} West"
            return _entity(seed, "decoy", names.entity_name(other, 0), start, months, size)[0]

        def rng_for(name: str) -> Random:
            return stream(seed, f"flaws:{name}")

        context = _flaws.Context(first, books, requests, rng_for, decoy)
        first, requests, flaw_records = _flaws.apply(context, requested)
    payloads: tuple[AdversarialPayload, ...] = ()
    if adversarial:
        first, payloads = _adversarial.apply(first, stream(seed, "adversarial"))
    return SyntheticClient(
        seed=seed,
        generator_version=GENERATOR_VERSION,
        name=names.client_name(base),
        client_entities=(first, *(entity for entity, _ in built[1:])),
        request_list=requests,
        manifest=Manifest(flaw_records, payloads),
    )
