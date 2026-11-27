# ac-test-author: notanaskhan
"""T-06-T57 (TASK-9039; T-06 §3 F5, F7, F8; DEC-6043): the security stage's entity-depth cases.
Row acceptance: "Each case runs in the security stage and fails on a deliberately leaked field in
a fixture branch."

- **Portal isolation:** no client principal holds the matrix actions behind the form preview, the
  draft K-1s or the other-entity workpapers. The graph and the §754 request's scope are
  T-06-T56's Postgres cases (F8, the portal never reaches the graph) and R-01's scoped room.
- **TRI and classification:** every field of T-06's new read models that carries tax return
  information is tagged TRI (`tri_paths`): form face values, K-1 names and boxes, the M-2 lines,
  the shareholder allocation, the provision lines and Part IX. The detector case below shows the
  check fails on a deliberately untagged field.
- **Offshore masking on form faces:** a TIN on a face prints only as its masked last four, and
  the full TIN never reaches the face (`masked_tin`; the sealed store keeps it).
- **Walls:** graph nodes, hand-off targets and banner links answer 404 behind a wall (T-06-T47,
  T-06-T56 and T-06-T45's Postgres cases); not repeated here."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Annotated

import pytest
import yaml
from pydantic import BaseModel

from abacus.kernel.classification import classified, tri_paths
from abacus.modules.tax import entity_depth_contract as depth
from abacus.modules.tax.form_pages_service import masked_tin

_MATRIX_DIR = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "permission-matrix"
MATRIX = yaml.safe_load((_MATRIX_DIR / "tax.yaml").read_text())["actions"]
CLIENT_ROLES = ("client_admin", "client_contributor", "link_principal", "third_party")
PORTAL_BARRED = (
    "form_preview.read",
    "form_preview.download_draft",
    "k1_package.read",
    "other_workpapers.read",
)
# Each new read model's fields that carry return information (T-06-T44, T-06-T52).
EXPECTED_TRI: dict[type[BaseModel], set[str]] = {
    depth.TaxDepthFieldOut: {"value"},
    depth.TaxDepthK1PreviewOut: {"name", "box_2"},
    depth.TaxDepthAaaLineOut: {"aaa", "pti", "e_and_p", "oaa"},
    depth.TaxDepthShareholderOut: {
        "name",
        "pct",
        "ordinary_income",
        "interest",
        "nondeductible",
        "distributions",
    },
    depth.TaxDepthReconItemOut: {"amount", "rate_effect"},
    depth.TaxDepthDeferredItemOut: {"temporary_difference", "rate", "amount"},
    depth.TaxDepthExpenseLineOut: {"total", "program", "management", "fundraising", "time_study"},
}


def _untagged(model: type[BaseModel], expected: set[str]) -> set[str]:
    """The fields expected to carry TRI that are not tagged so (a leak)."""
    return expected - set(tri_paths(model))


@pytest.mark.parametrize("action", PORTAL_BARRED)
def test_no_client_principal_reaches_the_preview_the_draft_k1s_or_the_workpapers(
    action: str,
) -> None:
    row = MATRIX[action]
    for role in CLIENT_ROLES:
        assert row.get(role, "deny") == "deny", (action, role)


@pytest.mark.parametrize("model", list(EXPECTED_TRI), ids=lambda m: m.__name__)
def test_every_new_return_field_is_tagged_tri(model: type[BaseModel]) -> None:
    assert _untagged(model, EXPECTED_TRI[model]) == set()


def test_the_check_fails_on_a_deliberately_leaked_field() -> None:
    """The fixture branch: a K-1 line whose box amount lost its TRI tag."""

    class LeakedK1(BaseModel):
        name: Annotated[str, classified("restricted", tri=True)]
        box_2: Annotated[Decimal, classified("internal")]  # deliberately untagged

    assert _untagged(LeakedK1, {"name", "box_2"}) == {"box_2"}


def test_a_tin_on_a_form_face_prints_only_masked() -> None:
    assert masked_tin("ein", "0287") == "••-•••0287"
    assert masked_tin("ssn", "4417") == "•••-••-4417"
    assert masked_tin("ein", None) is None  # nothing to print, never the full TIN
    leaked = masked_tin("ein", "0287")
    assert leaked is not None and not any(ch.isdigit() for ch in leaked[:-4])
