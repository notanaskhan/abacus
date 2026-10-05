"""AC-20: the document validator rejects broken frontmatter and dangling references."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from abacus_tools.quality import validate_docs as vd

ADR = """---
id: ADR-001
title: "First decision: a colon in the title"
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: amber
---
Body.
"""
ADR_INDEX = """# ADRs

| ID | Decision | Risk zone | Status |
|---|---|---|---|
| [ADR-001](ADR-001-first.md) | First decision | amber | accepted |
"""
SPEC = """---
id: SPEC-001
title: Spec
status: approved
owner: Founder
risk_zone: red
related_adrs: [ADR-001]
related_specs: []
created: 2026-10-04
updated: 2026-10-04
---
- **AC-1** Given a thing, then it works.
"""
TASK = """---
id: TASK-001
title: Task
spec: SPEC-001
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-progress
branch: b
worktree:
created: 2026-10-04
updated: 2026-10-04
---
"""

Edit = Callable[[str, str], None]
Write = Callable[[str, str], None]


@pytest.fixture
def pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Write:
    """A minimal valid docs pack under tmp_path; returns a writer for repo-relative files."""
    monkeypatch.setattr(vd, "REPO", tmp_path)
    monkeypatch.setattr(vd, "ADR_DIR", tmp_path / "docs" / "adr")
    monkeypatch.setattr(vd, "SPEC_DIR", tmp_path / "docs" / "specs")
    monkeypatch.setattr(vd, "TASK_DIR", tmp_path / "work" / "tasks")
    policies = (
        tmp_path / "docs" / "architecture" / "permission-matrix.yaml",
        tmp_path / "docs" / "architecture" / "dependency-allowlist.yaml",
    )
    monkeypatch.setattr(vd, "POLICY_FILES", policies)

    def write(rel: str, text: str) -> None:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    write("docs/adr/ADR-001-first.md", ADR)
    write("docs/adr/README.md", ADR_INDEX)
    write("docs/adr/_TEMPLATE.md", "<!-- template -->\n---\nid: ADR-XXX\n---\n")
    write("docs/specs/SPEC-001-spec.md", SPEC)
    write("work/tasks/TASK-001-task.md", TASK)
    write("docs/architecture/permission-matrix.yaml", "actions: {}\n")
    write("docs/architecture/dependency-allowlist.yaml", "python: {}\n")
    return write


@pytest.fixture
def edit(pack: Write) -> Edit:
    """Replace text in one of the pack's default documents."""
    defaults = {
        "docs/adr/ADR-001-first.md": ADR,
        "docs/adr/README.md": ADR_INDEX,
        "docs/specs/SPEC-001-spec.md": SPEC,
        "work/tasks/TASK-001-task.md": TASK,
    }

    def apply(old: str, new: str) -> None:
        for rel, text in defaults.items():
            if old in text:
                pack(rel, text.replace(old, new))
                return
        raise AssertionError(f"{old!r} not found in any default document")

    return apply


def test_ac20_clean_pack_passes(pack: Write) -> None:
    assert vd.validate() == []


def test_ac20_main_exits_1_on_violation(edit: Edit) -> None:
    edit("risk_zone: amber\n---\nBody.", "risk_zone: orange\n---\nBody.")
    assert vd.main() == 1


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("deciders: Founder\n", "", "ADR-001-first.md: missing required field 'deciders'"),
        ("owner: Founder\n", "", "SPEC-001-spec.md: missing required field 'owner'"),
        ("spec: SPEC-001\n", "", "TASK-001-task.md: missing required field 'spec'"),
    ],
)
def test_ac20_missing_field_is_reported(edit: Edit, old: str, new: str, expected: str) -> None:
    edit(old, new)
    assert any(e.endswith(expected) for e in vd.validate())


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("status: accepted\n", "status: maybe\n", "status 'maybe' is not valid"),
        ("status: approved\n", "status: shipped\n", "status 'shipped' is not valid"),
        ("status: in-progress\n", "status: doing\n", "status 'doing' is not valid"),
        ("risk_zone: red\n", "risk_zone: purple\n", "risk_zone must be one of"),
        ("date: 2026-10-04\n", "date: 4 Oct 2026\n", "'date' must be an ISO date"),
        ("date: 2026-10-04\n", "date: 2026-13-01\n", "frontmatter is not valid YAML"),
    ],
)
def test_ac20_bad_enum_or_date_is_reported(edit: Edit, old: str, new: str, expected: str) -> None:
    edit(old, new)
    assert any(expected in e for e in vd.validate())


def test_ac20_id_filename_mismatch_is_reported(edit: Edit) -> None:
    edit("id: SPEC-001\n", "id: SPEC-002\n")
    assert any("id 'SPEC-002' does not match the filename" in e for e in vd.validate())


def test_ac20_duplicate_id_is_reported(pack: Write) -> None:
    pack("docs/specs/SPEC-001-copy.md", SPEC)
    assert any("duplicate id 'SPEC-001'" in e for e in vd.validate())


def test_ac20_frontmatter_must_start_at_line_1(pack: Write) -> None:
    pack("docs/specs/SPEC-001-spec.md", "<!-- note -->\n" + SPEC)
    assert any("frontmatter must start at line 1" in e for e in vd.validate())


def test_ac20_invalid_yaml_is_reported_once(edit: Edit) -> None:
    edit('title: "First decision: a colon in the title"', "title: First decision: a colon")
    errors = vd.validate()
    assert len(errors) == 1
    assert "ADR-001-first.md: frontmatter is not valid YAML" in errors[0]


def test_ac20_dangling_related_adr_is_reported(edit: Edit) -> None:
    edit("related_adrs: [ADR-001]", "related_adrs: [ADR-001, ADR-404]")
    assert any("related_adrs entry 'ADR-404' does not exist" in e for e in vd.validate())


def test_ac20_dangling_related_spec_is_reported(edit: Edit) -> None:
    edit("related_specs: []", "related_specs: [SPEC-404]")
    assert any("related_specs entry 'SPEC-404' does not exist" in e for e in vd.validate())


def test_ac20_unknown_task_spec_is_reported(edit: Edit) -> None:
    edit("spec: SPEC-001", "spec: SPEC-404")
    assert any("spec 'SPEC-404' does not exist" in e for e in vd.validate())


def test_ac20_unknown_acceptance_criterion_is_reported(edit: Edit) -> None:
    edit("acceptance_criteria: [AC-1]", "acceptance_criteria: [AC-1, AC-9]")
    errors = vd.validate()
    assert any("acceptance criterion 'AC-9' is not defined" in e for e in errors)
    assert not any("'AC-1'" in e for e in errors)


def test_ac20_missing_superseding_adr_is_reported(edit: Edit) -> None:
    edit("status: accepted\n", "status: superseded by ADR-777\n")
    edit("| amber | accepted |", "| amber | superseded by ADR-777 |")
    assert any("superseding ADR-777 does not exist" in e for e in vd.validate())


def test_ac20_index_status_mismatch_is_reported(edit: Edit) -> None:
    edit("| amber | accepted |", "| amber | deprecated |")
    assert any("ADR-001 status 'deprecated' != frontmatter 'accepted'" in e for e in vd.validate())


def test_ac20_adr_missing_from_index_is_reported(pack: Write) -> None:
    pack("docs/adr/ADR-002-second.md", ADR.replace("ADR-001", "ADR-002"))
    assert any("ADR-002 is missing from the index" in e for e in vd.validate())


def test_ac20_index_row_without_file_is_reported(pack: Write) -> None:
    row = "| [ADR-003](ADR-003-ghost.md) | Ghost | red | accepted |\n"
    pack("docs/adr/README.md", ADR_INDEX + row)
    assert any("ADR-003 is in the index but has no ADR file" in e for e in vd.validate())


def test_ac20_unparseable_policy_file_is_reported(pack: Write) -> None:
    pack("docs/architecture/permission-matrix.yaml", "actions: [unclosed\n")
    assert any("permission-matrix.yaml: does not parse" in e for e in vd.validate())


def test_ac20_repository_docs_are_valid() -> None:
    assert vd.validate() == []
