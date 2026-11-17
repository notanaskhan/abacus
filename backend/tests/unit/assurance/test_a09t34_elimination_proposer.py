"""A-09-T34 (SPEC-658 F4; A-09 §6; DEC-5522): `consolidation.elimination_proposer` on Harlow & Pike
at 8/31/2026 (AUD-33). Code builds every candidate and amount (E1a 20,000,000; E1b 26,000,000; E2
18,000,000; E3 240,000 = the cited 1,000,000 x 24.0%, the margin 14,400,000 / 60,000,000; E4
2,400,000; E5 1,200,000); the model only writes words and names the E3 cell; an uncited E3 or a
number the model made up blocks its proposal; the tool only proposes and the agent may never
approve or post."""

from __future__ import annotations

import uuid
from decimal import Decimal

from abacus.modules.agents.specs._specs_v2 import SPECS_V2
from abacus.modules.assurance import elimination_proposer as ep
from abacus.modules.identity.authz.matrix import RULES

D = Decimal


def _e(key: str, name: str, level: int, parent: str | None, **lines: str) -> ep.EntityTb:
    captions = {
        "inv_opco": "Investment in Operating Co.",
        "inv_re": "Investment in Real Estate",
        "inv_mfg": "Investment in Manufacturing",
        "inv_dist": "Investment in Distribution",
        "capital": "Common stock / contributed capital",
        "rec": "Intercompany receivable",
        "pay": "Intercompany payable",
        "inventory": "Inventory",
        "sales": "Net sales \N{EM DASH} third party",
        "ic_sales": "Net sales \N{EM DASH} intercompany",
        "rent_income": "Rental income \N{EM DASH} intercompany",
        "cogs": "Cost of goods sold",
        "rent_expense": "Rent expense \N{EM DASH} intercompany",
    }
    return ep.EntityTb(
        key=key,
        client_entity_id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        name=name,
        level=level,
        parent_key=parent,
        lines={captions[k]: D(v) for k, v in lines.items()},
    )


HARLOW_PIKE = (
    _e("hold", "Harlow & Pike Holdings, Inc.", 1, None,
       inv_opco="20000000", inv_re="6000000", capital="-12000000"),
    _e("opco", "Harlow & Pike Operating Co.", 2, "hold",
       inv_mfg="14000000", inv_dist="6000000", capital="-20000000"),
    _e("mfg", "Harlow & Pike Manufacturing, LLC", 3, "opco",
       capital="-14000000", rec="2400000", inventory="9600000", sales="-42000000",
       ic_sales="-18000000", cogs="45600000", rent_expense="1200000"),
    _e("dist", "Harlow & Pike Distribution, LLC", 3, "opco",
       capital="-6000000", pay="-2400000", inventory="6300000", sales="-31000000",
       cogs="24800000"),
    _e("re", "Harlow & Pike Real Estate, LLC", 2, "hold",
       capital="-6000000", rent_income="-1200000"),
)  # fmt: skip


def _by_kind() -> dict[str, list[ep.Candidate]]:
    out: dict[str, list[ep.Candidate]] = {}
    for c in ep.candidates(HARLOW_PIKE):
        out.setdefault(c.kind, []).append(c)
    return out


def test_code_builds_e1a_e1b_e2_e4_e5_with_their_levels_and_amounts() -> None:
    found = _by_kind()
    investments = sorted((c.level, c.amount) for c in found["investment"])
    assert investments == [(1, D("26000000")), (2, D("20000000"))]  # E1b, E1a
    [sales] = found["intercompany_sales"]
    assert (sales.level, sales.amount) == (2, D("18000000"))
    [balances] = found["balances"]
    assert (balances.level, balances.amount) == (2, D("2400000"))
    [rent] = found["rent"]
    assert (rent.level, rent.amount) == (1, D("1200000"))
    for c in ep.candidates(HARLOW_PIKE):
        if c.kind != "unrealized_profit":
            assert sum(ln.debit for ln in c.lines) == sum(ln.credit for ln in c.lines)


def test_e3_is_the_cited_1_000_000_times_the_code_computed_24_0_percent() -> None:
    [e3] = _by_kind()["unrealized_profit"]
    seller = next(e for e in HARLOW_PIKE if e.key == "mfg")
    assert ep.seller_margin(seller) == D("14400000") / D("60000000") == D("0.24")
    done = ep.unrealized_profit(e3, D("1000000"))
    assert done.amount == D("240000")
    assert [(ln.caption, ln.debit, ln.credit) for ln in done.lines] == [
        ("Cost of goods sold", D("240000"), D("0")),
        ("Inventory", D("0"), D("240000")),
    ]
    assert D("24.0") in done.figures and D("1000000") in done.figures


def _answer(
    *, e3_cell: bool = True, e3_note: str = "Profit on goods still on hand."
) -> ep.ProposerOutput:
    entries: list[ep.ProposerEntry] = []
    for c in ep.candidates(HARLOW_PIKE):
        evidence = None
        if c.kind == "unrealized_profit" and e3_cell:
            evidence = ep.ProposerCell(sheet="By vendor", cell="C14")
        entries.append(
            ep.ProposerEntry(
                key=c.key,
                description=f"Eliminate {c.kind.replace('_', ' ')}",
                note=e3_note if c.kind == "unrealized_profit" else "Intercompany.",
                evidence=evidence,
            )
        )
    return ep.ProposerOutput(entries=entries)


def test_settle_keeps_all_six_with_the_cited_cell() -> None:
    given = ep.candidates(HARLOW_PIKE)
    e3 = next(c for c in given if c.kind == "unrealized_profit")
    settled = ep.settle(_answer(), given, {e3.key: D("1000000")})
    assert len(settled.kept) == 6 and settled.blocked == ()
    kept_e3 = next(k for k in settled.kept if k.candidate.kind == "unrealized_profit")
    assert kept_e3.candidate.amount == D("240000")


def test_an_uncited_number_blocks_the_proposal() -> None:
    given = ep.candidates(HARLOW_PIKE)
    e3 = next(c for c in given if c.kind == "unrealized_profit")
    no_cell = ep.settle(_answer(e3_cell=False), given, {e3.key: D("1000000")})
    assert (e3.key, "uncited_number") in no_cell.blocked
    unread = ep.settle(_answer(), given, {e3.key: None})
    assert (e3.key, "uncited_number") in unread.blocked
    made_up = ep.settle(_answer(e3_note="About 250,000 of profit."), given, {e3.key: D("1000000")})
    assert (e3.key, "number_not_from_code") in made_up.blocked


def test_a_one_sided_pair_is_not_proposed() -> None:
    lopsided = [*HARLOW_PIKE[:3], _e("dist", "Harlow & Pike Distribution, LLC", 3, "opco",
                                     capital="-6000000", pay="-2300000", cogs="24800000"),
                HARLOW_PIKE[4]]  # fmt: skip
    kinds = {c.kind for c in ep.candidates(lopsided)}
    assert "balances" not in kinds and "intercompany_sales" not in kinds


def test_the_model_never_sees_e3_s_amount_and_the_run_only_proposes() -> None:
    given = ep.candidates(HARLOW_PIKE)
    shown = ep.model_input(given, {e.key: e.name for e in HARLOW_PIKE})
    e3 = next(c for c in shown.candidates if c.kind == "unrealized_profit")
    assert all(line.amount is None for line in e3.lines)
    spec = SPECS_V2[ep.CAPABILITY]
    assert spec["tools"] == {"propose": [ep.PROPOSE_TOOL]}
    assert spec["autonomy"] == "propose" and spec["client_data"] == "none"
    for action in ("elimination.approve", "elimination.apply", "elimination.edit"):
        assert RULES[action].decisions.get("agent") == "deny"
    assert RULES["elimination.agent_propose"].decisions.get("agent") == "task_scope"
    assert {
        r for r, d in RULES["elimination.agent_propose"].decisions.items() if d == "allow"
    } == set()
