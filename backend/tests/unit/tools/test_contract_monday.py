"""F-09-T124: the Contract Monday note lists every open application with its status and the
register's triggers to check that day.

Acceptance: the note lists every open application, contract and partner with its status, and any
fired trigger has its pre-agreed action that day. The tool reads the tracker and the register only:
it lists open rows (not approved, not needed), flags those past their Needed-by date, copies each
named trigger's signal and contingency, and leaves "Fired?" to a person.
"""

from __future__ import annotations

from datetime import date

from abacus_tools import contract_monday as cm

TRACKER = """# Tracker
## Platform

| Application | Needed for | Start | Needed by | Gate | Fallback if late | Status | Vault |
|---|---|---|---|---|---|---|---|
| WorkOS order form | sign-in | Oct 19 | Nov 13 | M2 | fake OIDC | approved | V-007 |
| Temporal Cloud account | everything | Oct 19 | Nov 6 | M2 | — | filed | V-009 |
| Bedrock entry | AI | Oct 26 | Dec 11 (draft); then M7 | M4 | off | to file | |
| DocuSign ID Verification | 8879 | Jan 4 | Jun 18, 2027 | M11 | handwritten | not needed | |
"""

REGISTER = """## Triggers

| ID | Early-warning signal | Mitigation | Contingency (trigger → action) |
|---|---|---|---|
| RK-05 | Spend above the envelope | ledger | **two months over** → cut the spill list |
| RK-01 | Fewer than 2 LOIs at M3 | outreach | **< 2 LOIs** → Pilot 0 on synthetic data |
"""


def test_only_open_rows_are_listed_and_late_ones_are_flagged() -> None:
    apps = cm.applications(TRACKER)
    text = cm.note("S15", date(2026, 11, 10), apps, [])
    assert "WorkOS" not in text and "DocuSign" not in text  # approved, not needed
    temporal = next(line for line in text.splitlines() if "Temporal Cloud" in line)
    bedrock = next(line for line in text.splitlines() if "Bedrock entry" in line)
    assert temporal.endswith("| **yes** |")  # Nov 6 < Nov 10
    assert bedrock.endswith("|  |")  # Dec 11 is still ahead
    assert "**Open:** 2 of 4 · **past Needed by:** 1" in text


def test_needed_by_reads_the_plans_year() -> None:
    apps = {a.name: a for a in cm.applications(TRACKER)}
    assert apps["Temporal Cloud account"].due() == date(2026, 11, 6)
    assert apps["DocuSign ID Verification"].due() == date(2027, 6, 18)
    assert apps["Bedrock entry"].due() == date(2026, 12, 11)


def test_triggers_come_from_the_register_in_the_order_asked() -> None:
    found = cm.triggers(REGISTER, ["RK-01", "RK-05", "RK-99"])
    assert [t.rk for t in found] == ["RK-01", "RK-05", "RK-99"]
    assert found[0].contingency.startswith("**< 2 LOIs**")
    assert found[2].signal == "not in the register"
    text = cm.note("S15", date(2027, 5, 17), [], found)
    assert (
        "| RK-01 | Fewer than 2 LOIs at M3 |" in text and "| — | — |" in text
    )  # Fired? left blank


def test_the_note_never_holds_more_than_the_tracker_does() -> None:
    text = cm.note(
        "S15", date(2027, 5, 17), cm.applications(TRACKER), cm.triggers(REGISTER, ["RK-05"])
    )
    assert "$" not in text  # no amounts: the ledger's figures stay in the vault
    assert "Spend ledger refreshed against the envelope (amounts stay in the vault)" in text


def test_the_committed_tracker_and_register_parse() -> None:
    apps = cm.applications(cm.TRACKER.read_text(encoding="utf-8"))
    rks = cm.triggers(cm.REGISTER.read_text(encoding="utf-8"), list(cm.DEFAULT_RKS))
    assert apps and all(a.name for a in apps)
    assert all(t.signal != "not in the register" for t in rks), [t.rk for t in rks]
