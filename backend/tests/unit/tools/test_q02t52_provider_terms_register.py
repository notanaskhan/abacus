# ac-test-author: ayushkbhatia
"""Q-02-T52 (ADR-078) for Q-02-T18: the provider terms register needs counsel as a second
approver, and the compiled module may not drift from the register.

Promises (ADR-114 §1 and §3, Q3; Q-02 §3 item 3, gate G-2; Q-02-T18; F-09-T47): an entry
approved by the founder alone no longer compiles, because ADR-114 Q3 adds counsel as a second
approver before the first paying firm and Q-02's gate G-2 asks for "a current register entry with
counsel as second approver"; the compiled `kernel/_provider_terms.py` matches the YAML, and a
planted difference is reported; an entry past `review_by` covers nothing (boot validation).

The field that records counsel's approval is not named by any spec, so the seeded violation is
written without it: an entry that satisfies every other ADR-114 field, approved by the founder
only. Whatever T18 calls the field, that entry must be refused. Boundary: the codegen's public
`validate`, `render` and `main(["--check"])`, and `kernel.provider_terms.covering`.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from abacus.kernel import _provider_terms
from abacus.kernel.provider_terms import TermsEntry, covering
from abacus_tools.codegen import provider_terms as codegen
from abacus_tools.codegen.provider_terms import TermsInvalid, render, validate

APPROVED = date(2026, 12, 11)
REVIEW_BY = date(2027, 12, 1)


def _founder_only_entry() -> dict[str, object]:
    """Every ADR-114 §1 field, current and valid, approved by the founder and nobody else."""
    return {
        "route": "bedrock",
        "provider": "Amazon Web Services",
        "documents": [
            {"title": "AWS Customer Agreement", "version": "2026-09", "accepted_on": APPROVED},
            {"title": "AWS Service Terms", "version": "2026-09", "accepted_on": APPROVED},
            {
                "title": "AWS Data Processing Addendum",
                "version": "2026-09",
                "accepted_on": APPROVED,
            },
        ],
        "training": "none",
        "retention": {"beyond_processing": False, "exceptions": []},
        "region": "us-east-2",
        "subprocessors": [],
        "breach_notice": "Without undue delay",
        "approved_by": "founder",
        "approved_on": APPROVED,
        "review_by": REVIEW_BY,
    }


# --- the second approver (ADR-114 Q3; Q-02-T18) --------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1231: Q-02-T18 is not built on main; the register schema has no second approver, "
        "so an entry approved by the founder alone still validates (ADR-114 Q3, Q-02 gate G-2; "
        "found on main at #397)"
    ),
)
def test_t18_an_entry_approved_by_the_founder_alone_is_refused() -> None:
    with pytest.raises(TermsInvalid):
        validate(_founder_only_entry())


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1231: Q-02-T18 is not built on main; a register holding a founder-only entry still "
        "compiles into kernel/_provider_terms.py (ADR-114 Q3, Q-02-T52 seeded violation; #397)"
    ),
)
def test_t18_a_register_holding_a_founder_only_entry_does_not_compile() -> None:
    source = yaml.safe_dump({"entries": [_founder_only_entry()]}, sort_keys=False)
    with pytest.raises(TermsInvalid):
        render(source)


def test_t18_the_founder_alone_is_still_required_as_an_approver() -> None:
    """Counsel is a second approver, not a replacement: an entry without the founder is refused."""
    entry = {**_founder_only_entry(), "approved_by": "counsel"}
    with pytest.raises(TermsInvalid):
        validate(entry)


# --- the drift check (ADR-114 §3) ----------------------------------------------------------------


def test_t18_the_committed_module_passes_the_drift_check() -> None:
    assert codegen.main(["--check"]) == 0
    assert codegen.TARGET.read_text() == render(codegen.SOURCE.read_text())


def test_t18_a_planted_difference_fails_the_drift_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "provider-terms.yaml"
    source.write_text(codegen.SOURCE.read_text())
    target = tmp_path / "_provider_terms.py"
    compiled = codegen.TARGET.read_text()
    assert "ENTRIES" in compiled
    # A hand edit of the generated module: one entry that the register does not hold.
    target.write_text(compiled.replace("= ()", "= (None,)", 1) + "\n# hand edit\n")
    monkeypatch.setattr(codegen, "BACKEND", tmp_path)  # the report names the module from here
    monkeypatch.setattr(codegen, "SOURCE", source)
    monkeypatch.setattr(codegen, "TARGET", target)
    assert codegen.main(["--check"]) == 1
    assert target.read_text() != render(source.read_text())


def test_t18_a_missing_module_fails_the_drift_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "provider-terms.yaml"
    source.write_text(codegen.SOURCE.read_text())
    monkeypatch.setattr(codegen, "BACKEND", tmp_path)
    monkeypatch.setattr(codegen, "SOURCE", source)
    monkeypatch.setattr(codegen, "TARGET", tmp_path / "absent.py")
    assert codegen.main(["--check"]) == 1


# --- review_by (ADR-114 §3: past review_by, the route carries no client data) --------------------


def test_t18_an_entry_covers_its_route_only_until_review_by(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = TermsEntry(
        route="bedrock",
        provider="Amazon Web Services",
        region="us-east-2",
        approved_on=APPROVED,
        review_by=REVIEW_BY,
    )
    monkeypatch.setattr(_provider_terms, "ENTRIES", (entry,))
    assert covering("bedrock", REVIEW_BY) == entry
    assert covering("bedrock", REVIEW_BY + timedelta(days=1)) is None
    assert covering("bedrock", APPROVED - timedelta(days=1)) is None
    assert covering("direct", REVIEW_BY) is None  # ADR-113: only Bedrock is ever eligible


def test_t18_a_review_more_than_twelve_months_out_is_refused() -> None:
    with pytest.raises(TermsInvalid):
        validate({**_founder_only_entry(), "review_by": APPROVED + timedelta(days=400)})
