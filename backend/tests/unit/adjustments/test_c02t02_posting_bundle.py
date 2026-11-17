"""C-02-T02 (SPEC-700 AC-1, AC-10; ADR-344; DEC-5501): the S49 protected bundle.

The W1 registry entry declares its whole posting policy and stays off; only W1 carries it; the
agent is denied every new posting, delivery and write-grant action; POST-001, TJE-001 and IRIS-001
find what they ban; every new fresh-MFA action carries the condition.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from abacus.kernel import _flags
from abacus.modules.identity.authz.matrix import ACTIONS
from abacus.modules.integrations import _capabilities as caps
from abacus.modules.integrations.api import WriteCapabilityEntry
from abacus_tools.quality import banned_patterns as bp

NEW_ACTIONS = (
    "proposed_entry.approve",
    "proposed_entry.request_approval",
    "proposed_entry.undo_approval",
    "proposed_entry.withdraw_approval",
    "proposed_entry.reject_close",
    "proposed_entry.record_external",
    "proposed_entry.export",
    "posting_batch.dry_run",
    "posting_batch.post",
    "closing_date_conflict.resolve",
    "write_capability.enable",
    "gl_posting_settings.read",
    "gl_posting_settings.update",
    "engagement_ledger_settings.update",
    "ledger_connection.read",
    "ledger_connection.export",
    "connection.grant_write",
    "connection.revoke_write",
    "close_package.read",
    "close_package.edit",
    "close_package.generate",
    "close_package.export",
    "close_package.release",
    "close.lock",
    "close.reopen",
    "tax_handoff.read",
    "tax_handoff.publish",
    "information_returns.read",
    "vendor_1099.update",
    "w9.request",
    "tin_match.record",
    "backup_withholding.record",
    "information_return_batch.approve",
    "information_return_batch.export",
    "information_return_batch.record_filing",
    "information_return_batch.record_ack",
)
W1 = {
    "key": "ledger_post_journal_entries",
    "adapter_key": "quickbooks_online_poster",
    "shape": "W1",
    "owner_epic": "C-02",
    "decision": "ADR-344",
    "operations": ["create_journal_entry", "set_closing_date"],
    "attest_clients": "refused",
    "policy_principal": "never",
    "preflight": [
        "balanced",
        "open_period",
        "mapped_accounts",
        "active_accounts",
        "closing_date_unlocked",
    ],
    "verify_after": "read_back",
    "reversal": "new_write",
    "kill_switch": "write.ledger.post_journal_entries",
}


def test_ac1_the_w1_entry_declares_its_policy_and_stays_off() -> None:
    entry = next(w for w in caps.WRITES if w["key"] == "ledger_post_journal_entries")
    assert entry["enabled"] is False
    assert entry["decision"] == "ADR-344"
    assert entry["operations"] == ("create_journal_entry", "set_closing_date")
    assert entry["attest_clients"] == "refused"
    assert entry["policy_principal"] == "never"
    assert entry["kill_switch"] == "write.ledger.post_journal_entries"


def test_ac1_only_w1_carries_the_policy_and_w1_cannot_open() -> None:
    WriteCapabilityEntry.model_validate(W1)
    with pytest.raises(ValidationError):
        WriteCapabilityEntry.model_validate({**W1, "enabled": True})  # W1 is not openable
    with pytest.raises(ValidationError):
        WriteCapabilityEntry.model_validate({**W1, "operations": ["update_transaction"]})
    with pytest.raises(ValidationError):
        WriteCapabilityEntry.model_validate({**W1, "preflight": ["balanced"]})
    missing = {k: v for k, v in W1.items() if k != "attest_clients"}
    with pytest.raises(ValidationError):
        WriteCapabilityEntry.model_validate(missing)
    with pytest.raises(ValidationError):
        WriteCapabilityEntry.model_validate(
            {**W1, "key": "other", "shape": "W2", "operations": None, "attest_clients": None}
        )


@pytest.mark.parametrize("action", NEW_ACTIONS)
def test_ac10_the_agent_and_system_are_denied_every_new_action(action: str) -> None:
    cells = ACTIONS[action]
    assert cells.get("agent") == "deny"
    assert cells.get("system") == "deny"


@pytest.mark.parametrize(
    "action",
    [
        "posting_batch.post",
        "write_capability.enable",
        "gl_posting_settings.update",
        "connection.grant_write",
        "connection.revoke_write",
        "close_package.release",
        "close.lock",
    ],
)
def test_the_external_effect_actions_need_a_fresh_second_factor(action: str) -> None:
    assert ACTIONS[action].get("mfa_recent") == "required"


def test_the_six_rollout_flags_exist_and_default_off() -> None:
    names = (
        "adjustments.posting",
        "closes.gl_console",
        "closes.delivery",
        "closes.tax_handoff",
        "closes.information_returns",
        "closes.vendor_screen",
    )
    for name in names:
        flag = getattr(_flags, name.replace(".", "_").upper())
        assert flag.name == name
        assert flag.default == "false"


def _count(root: Path, rule: str, rel: str, source: str) -> int:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return len([v for v in bp.scan(root) if v.rule_id == rule and v.path == rel])


def test_post_001_refuses_the_w1_capability_outside_posting(tmp_path: Path) -> None:
    source = 'CAP = "ledger_post_journal_entries"\n'
    assert _count(tmp_path, "POST-001", "src/abacus/modules/closes/release.py", source) == 1
    assert _count(tmp_path, "POST-001", "src/abacus/modules/adjustments/posting.py", source) == 0
    call = "async def f(api):\n    await api.execute_write('x')\n"
    assert _count(tmp_path, "POST-001", "src/abacus/modules/adjustments/entries.py", call) == 1


def test_tje_001_refuses_a_tax_only_entry_in_posting_code(tmp_path: Path) -> None:
    rel = "src/abacus/modules/adjustments/posting_workflows.py"
    assert _count(tmp_path, "TJE-001", rel, 'KINDS = ("aje", "tje")\n') == 1
    assert _count(tmp_path, "TJE-001", rel, 'KINDS = ("aje", "rje")\n') == 0


@pytest.mark.parametrize(
    "source",
    [
        'HOST = "https://la.www4.irs.gov/iris"\n',
        'ROUTE = "/v1/information-return-batches/{id}/transmit"\n',
        "tcc_code = 1\n",
    ],
)
def test_iris_001_refuses_an_irs_host_a_tcc_or_a_transmit_route(
    tmp_path: Path, source: str
) -> None:
    rel = "src/abacus/modules/closes/information_returns.py"
    assert _count(tmp_path, "IRIS-001", rel, source) >= 1
