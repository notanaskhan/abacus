# ac-test-author: notanaskhan
"""T-08-T35 (TASK-9038; ADR-078; SPEC-710; DEC-6042): independent AC suite #2 on AY's amber
practice-tool code, black box at its seams. Row acceptance: the SPEC ACs for TAX-14, TAX-15 and
TAX-16 with INV-1 (agents propose, people decide), INV-2 (the version a result came from) and
INV-5 (attribution).

- Planning's §7216 filter: a tax service is Open with consent and Not screened without; another
  product without its consent is never written.
- People decide (INV-1): raise, create project and dismiss are a live person's acts; the agent
  and the system are denied in the matrix; a dismissal needs a reason.
- Amendments: the as-filed baseline is the original's approved checkpoint (409
  `baseline_unavailable` without one); supersession is insert-only, once, on the amendment's
  accepted federal ack.
- The BBA election is reserved to the client's signer and stored by a human only (the CHECK).
TAX-14's standards dedupe moved to T-08-T38 with T14 (the row says so)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import ValidationError

from abacus.modules.identity.api import Forbidden
from abacus.modules.tax import amendment_gates, amendments
from abacus.modules.tax.planning import service as planning
from abacus.modules.tax.practice_tools_contract import TaxPracticeDismissIn

BACKEND = Path(__file__).resolve().parents[3]
MATRIX = yaml.safe_load(
    (BACKEND.parent / "docs" / "architecture" / "permission-matrix" / "tax.yaml").read_text()
)["actions"]


@pytest.mark.parametrize(
    ("product", "tri", "other", "status"),
    [
        ("tax_service", True, False, "open"),
        ("tax_service", False, False, "not_screened"),
        ("non_tax_product", True, False, None),
        ("non_tax_product", True, True, "open"),
        ("non_tax_product", False, True, "not_screened"),
    ],
)
def test_ac_the_7216_filter(product: str, tri: bool, other: bool, status: str | None) -> None:
    assert planning.consent_status(product, tri, other) == status


@pytest.mark.parametrize(
    "action", ["planning.raise", "planning.create_project", "planning.dismiss"]
)
def test_ac_inv1_agents_and_the_system_never_decide_an_opportunity(action: str) -> None:
    row = MATRIX[action]
    assert row.get("agent") == "deny" and row.get("system") == "deny"
    assert row.get("client_admin") == "deny" and row.get("link_principal") == "deny"


@pytest.mark.parametrize(
    "actor",
    [
        SimpleNamespace(
            tenant=SimpleNamespace(actor_kind="agent"), client=False, is_support=False
        ),
        SimpleNamespace(
            tenant=SimpleNamespace(actor_kind="system"), client=False, is_support=False
        ),
        SimpleNamespace(tenant=SimpleNamespace(actor_kind="human"), client=True, is_support=False),
        SimpleNamespace(tenant=SimpleNamespace(actor_kind="human"), client=False, is_support=True),
    ],
)
def test_ac_inv1_only_a_live_firm_person_raises(actor: object) -> None:
    with pytest.raises(Forbidden):
        planning._human(actor, "planning.raise")  # type: ignore[arg-type] -- a stand-in actor
    person = SimpleNamespace(
        tenant=SimpleNamespace(actor_kind="human"), client=False, is_support=False
    )
    planning._human(person, "planning.raise")  # type: ignore[arg-type] -- a stand-in person


def test_ac_a_dismissal_needs_a_reason() -> None:
    with pytest.raises(ValidationError):
        TaxPracticeDismissIn.model_validate({})
    assert TaxPracticeDismissIn.model_validate({"reason": "not_suitable"}).reason == "not_suitable"


def test_ac_inv2_the_baseline_is_the_originals_approved_checkpoint() -> None:
    """No approved checkpoint, no amendment: 409 `baseline_unavailable`; the row names the
    checkpoint it was built from (INV-2)."""
    assert amendments.BaselineUnavailable.code == "baseline_unavailable"
    source = Path(amendments.__file__).read_text()
    assert "baseline_checkpoint_id" in source
    assert 'current_checkpoint(ctx.tenant, "tax_return", original_id)' in source


def test_ac_supersession_is_insert_only_and_once() -> None:
    source = Path(amendments.__file__).read_text()
    insert = source[source.index("_SUPERSEDE: Final = text(") :]
    insert = insert[: insert.index(")\n\n")]
    assert "INSERT INTO return_supersessions" in insert
    assert "ON CONFLICT (tenant_id, original_work_item_id) DO NOTHING" in insert
    assert (
        "UPDATE return_supersessions" not in source
        and "DELETE FROM return_supersessions" not in source
    )


def test_ac_the_bba_election_is_the_signers_and_a_humans() -> None:
    source = Path(amendment_gates.__file__).read_text()
    assert "reserved to the client's signer" in source and "signer_for" in source
    migration = (BACKEND / "migrations" / "versions" / "0961_tax_practice_tools.py").read_text()
    election = migration[migration.index('("aar_elections"') :]
    election = election[: election.index("True),")]
    assert "{_HUMAN}" in election  # the CHECK holds the election human (INV-1)
    assert MATRIX["aar.create"].get("agent") == "deny"
