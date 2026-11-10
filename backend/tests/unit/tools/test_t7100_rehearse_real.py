"""TASK-7100 (DEC-4100): the synthetic test pilot firm rehearses the real-firm clauses.

From the decision: `tenant.real` passes for PF-X1 only in a run labelled a rehearsal, never for a
real firm and never silently; the dossier's `--ready` acceptance can be rehearsed on a `PF-X…`
dossier with synthetic evidence, while plain `--ready` keeps refusing both the rehearsal's stamp
and any `green (synthetic)` row, so PF-X1 never reads ready as a real firm and a real firm's
dossier never accepts synthetic evidence.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from uuid import UUID

import pytest

from abacus_tools import go_live, release_windows
from abacus_tools import go_live_dossier as gd
from abacus_tools.go_live import Facts, evaluate, report

PF_X1 = UUID("293fc3e7-be13-4767-ae6a-ce245b2dbda9")
AT = datetime.fromisoformat("2027-05-27T10:00:00-05:00")
TODAY = date(2027, 5, 28)

SYNTHETIC = Facts(
    tenant_id=PF_X1,
    synthetic=True,
    provisioned=True,
    pilot_code="PF-X1",
    sso_enforced=True,
    sso_exempt_designated=True,
    mfa_enrolled=46,
    mfa_seats=46,
    firm_admins=2,
    security_admins=1,
    support_requests_allowed=True,
    ai_opted_in=True,
    agent_stages={"evidence.screener": "shadow"},
    flags_on=frozenset({"engagements.v2"}),
    terms_review_by=(date(2027, 12, 31),),
    writes_enabled=0,
    flag_expiries={"engagements.v2": date(2027, 8, 20)},
    runbooks_rehearsed={"RB-16": date(2027, 8, 1)},
    on_call_updated=date(2027, 5, 20),
)


def _real(items: list[go_live.Item]) -> go_live.Item:
    return next(i for i in items if i.id == "tenant.real")


def test_tenant_real_still_fails_for_the_synthetic_firm_by_default() -> None:
    item = _real(evaluate("shadow", SYNTHETIC, AT, release_windows.load()))
    assert (item.status, item.value) == ("fail", "synthetic")


def test_a_rehearsal_passes_tenant_real_and_says_so() -> None:
    items = evaluate("shadow", SYNTHETIC, AT, release_windows.load(), rehearse_real=True)
    item = _real(items)
    assert item.status == "pass"
    assert item.value == "synthetic (PF-X1): rehearsed as real"
    out = report("shadow", SYNTHETIC, AT, items, rehearsal=True)
    assert out["rehearsal"] is True
    assert "rehearsal" not in report("shadow", SYNTHETIC, AT, items)


def test_a_real_firm_is_never_rehearsed() -> None:
    real = replace(SYNTHETIC, synthetic=False, pilot_code="PF-A1")
    with pytest.raises(ValueError, match="synthetic firm only"):
        evaluate("shadow", real, AT, release_windows.load(), rehearse_real=True)


def test_the_cli_refuses_a_rehearsal_for_a_firm_not_listed_synthetic() -> None:
    other = "00000000-0000-4000-8000-0000000000a1"
    assert go_live.main(["--firm", other, "--level", "shadow", "--rehearse-real"]) == 2


def _ready_text(*, rehearsal: bool, state: str, ack: str) -> str:
    items = [
        {"id": "tenant.real", "section": "Tenant", "status": "pass", "value": "x", "dossier": ""}
    ]
    rep: dict[str, object] = {
        "level": "shadow",
        "at": AT.isoformat(),
        "passed": True,
        "failed": [],
        "items": items,
    }
    if rehearsal:
        rep["rehearsal"] = True
    text = gd.fill(gd.template("PF-X1"), rep)
    lines: list[str] = []
    for line in text.splitlines():
        cells = line.split(" | ")
        if line.startswith("| ") and len(cells) == 4 and cells[-1] == "— |" and "-" in cells[0]:
            line = " | ".join([*cells[:2], "V-SYN-1", f"{state} |"])
        lines.append(line)
    text = "\n".join(lines)
    return text.replace("| — | — | — |", ack, 1)


SYN_ACK = "| 2027-05-26 | v1 | synthetic (PF-X1) V-SYN-ACK |"


def test_the_rehearsal_stamp_is_written_by_fill() -> None:
    text = _ready_text(rehearsal=True, state=gd.SYNTHETIC_GREEN, ack=SYN_ACK)
    assert "passed (rehearsal, synthetic, DEC-4100) |" in text


def test_ready_rehearsal_accepts_synthetic_evidence_on_pf_x1() -> None:
    text = _ready_text(rehearsal=True, state=gd.SYNTHETIC_GREEN, ack=SYN_ACK)
    assert gd.not_ready("PF-X1", text, TODAY, rehearsal=True) == []


def test_plain_ready_refuses_the_rehearsal_and_synthetic_rows() -> None:
    text = _ready_text(rehearsal=True, state=gd.SYNTHETIC_GREEN, ack=SYN_ACK)
    problems = gd.not_ready("PF-X1", text, TODAY)
    assert any("is a rehearsal, not a real firm's" in p for p in problems)
    assert any("contract-1 is not green" in p for p in problems)


def test_a_rehearsal_needs_a_rehearsal_stamp_and_a_synthetic_acknowledgement() -> None:
    real_stamp = _ready_text(rehearsal=False, state=gd.SYNTHETIC_GREEN, ack=SYN_ACK)
    assert any(
        "needs a rehearsal go-live check" in p
        for p in gd.not_ready("PF-X1", real_stamp, TODAY, rehearsal=True)
    )
    plain_ack = _ready_text(
        rehearsal=True, state=gd.SYNTHETIC_GREEN, ack="| 2027-05-26 | v1 | V-ACK |"
    )
    assert any(
        "names its synthetic entry" in p
        for p in gd.not_ready("PF-X1", plain_ack, TODAY, rehearsal=True)
    )


def test_a_real_firm_dossier_cannot_be_rehearsed_or_filled_from_a_rehearsal(
    tmp_path: object,
) -> None:
    text = _ready_text(rehearsal=True, state=gd.SYNTHETIC_GREEN, ack=SYN_ACK)
    assert gd.not_ready("PF-A1", text, TODAY, rehearsal=True) == [
        "PF-A1: --rehearsal is for the synthetic test firm only (PF-X…, DEC-4100)"
    ]
    assert gd.main(["check", "--ready", "--rehearsal"]) == 2  # one PF-X… dossier, named


def test_the_committed_pf_x1_dossier_still_never_reads_ready_as_a_real_firm() -> None:
    text = (gd.DOSSIERS / "PF-X1.md").read_text(encoding="utf-8")
    assert gd.not_ready("PF-X1", text, TODAY) != []
