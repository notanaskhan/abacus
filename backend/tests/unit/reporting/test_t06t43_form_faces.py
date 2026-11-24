"""T-06-T43 (TASK-8912; SPEC-702 F7; TAX-11; DEC-5914): form faces as `tax_form_face` templates.

Row acceptance: "Each template validates against the field-manifest schema, and the import dry-run
diff is empty on a second load." Here: the family needs its manifest and layout (and no other
family may carry one); the manifest's rules (pages, keys, boxes, binding shapes, TIN masks); the
manifest is content (its hash changes the template's); a dry run against a latest version with
the same hash reports no change, a new template `new_template`, a changed manifest its fields.
The drafts themselves live outside the repository and pass `abacus_tools.form_faces` (recorded in
TASK-8912).
"""

from __future__ import annotations

from typing import Any

import pytest

from abacus.modules.reporting import templates as t
from abacus.modules.reporting.contract import TemplateImportIn


def _face(**manifest: Any) -> TemplateImportIn:  # noqa: ANN401 -- test overrides
    base: dict[str, Any] = {
        "form": "1065", "tax_year": 2025,
        "pages": [{"page_key": "p1", "page_no": 1, "title": "Form 1065 page 1"}],
        "fields": [
            {"key": "d", "page_key": "p1", "label": "D Employer identification number",
             "box": [0.76, 0.10, 0.96, 0.12], "format": "tin",
             "binding": {"kind": "return_fact", "ref": "entity.ein"}, "mask": True},
            {"key": "f", "page_key": "p1", "label": "F Total assets",
             "box": [0.76, 0.16, 0.96, 0.18], "format": "whole_dollars",
             "binding": {"kind": "tb_line", "ref": "L14"}},
            {"key": "k_1", "page_key": "p1", "label": "1 Ordinary business income (loss)",
             "box": [0.62, 0.30, 0.86, 0.32], "format": "whole_dollars",
             "binding": {"kind": "tb_line", "ref": "K 1"}},
        ],
    }  # fmt: skip
    base.update(manifest)
    return TemplateImportIn.model_validate(
        {
            "family": "tax_form_face",
            "name": "Form 1065 (TY2025)",
            "layout_key": "tax_form_face",
            "body": [],
            "field_manifest": base,
        }
    )


def _codes(body: TemplateImportIn) -> set[tuple[str, str]]:
    return {(e.path, e.code) for e in t.validate(body)[0]}


def test_a_valid_face_validates() -> None:
    assert _codes(_face()) == set()


def test_the_family_needs_its_manifest_and_layout() -> None:
    bare = _face().model_copy(update={"field_manifest": None})
    assert ("field_manifest", "field_manifest_required") in _codes(bare)
    wrong = _face().model_copy(update={"layout_key": "report"})
    assert ("layout_key", "unknown_layout") in _codes(wrong)
    letter = _face().model_copy(update={"family": "engagement_letter", "layout_key": "letter"})
    assert ("field_manifest", "field_manifest_required") in _codes(letter)


@pytest.mark.parametrize(
    ("change", "path"),
    [
        ({"box": [0.9, 0.1, 0.8, 0.12]}, "field_manifest.fields[1].box"),
        ({"page_key": "p9"}, "field_manifest.fields[1].page_key"),
        ({"binding": {"kind": "workbook_cell", "ref": "sheet six"}},
         "field_manifest.fields[1].binding.ref"),
        ({"mask": True}, "field_manifest.fields[1].mask"),
        ({"label": "See https://irs.gov"}, "field_manifest.fields[1].label"),
    ],
)  # fmt: skip
def test_the_manifest_rules(change: dict[str, Any], path: str) -> None:  # Any: overrides
    face = _face()
    assert face.field_manifest is not None
    fields = [f.model_dump(mode="json") for f in face.field_manifest.fields]
    fields[1] = {**fields[1], **change}
    assert (path, "field_manifest_invalid") in _codes(_face(fields=fields))


def test_an_unmasked_tin_is_refused() -> None:
    face = _face()
    assert face.field_manifest is not None
    fields = [f.model_dump(mode="json") for f in face.field_manifest.fields]
    fields[0] = {**fields[0], "mask": False}
    assert ("field_manifest.fields[0].mask", "field_manifest_invalid") in _codes(
        _face(fields=fields)
    )


def test_duplicate_keys_are_refused() -> None:
    face = _face()
    assert face.field_manifest is not None
    fields = [f.model_dump(mode="json") for f in face.field_manifest.fields]
    fields[2] = {**fields[2], "key": "f"}
    assert ("field_manifest.fields[2].key", "field_manifest_invalid") in _codes(
        _face(fields=fields)
    )


def test_the_manifest_is_content() -> None:
    face = _face()
    assert face.field_manifest is not None
    moved = [f.model_dump(mode="json") for f in face.field_manifest.fields]
    moved[1] = {**moved[1], "box": [0.70, 0.16, 0.96, 0.18]}
    assert t.content_sha256(face) != t.content_sha256(_face(fields=moved))
    assert t.content_sha256(face) == t.content_sha256(_face())


async def test_a_second_load_reports_no_change(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.methodology import api as methodology

    face = _face()
    stored: dict[str, object] = {"sha": None, "manifest": None}

    async def latest(*_: object) -> object:
        return None if stored["sha"] is None else (stored["sha"], stored["manifest"])

    monkeypatch.setattr(methodology, "latest_report_template_content", latest)
    assert await t._changes(object(), face) == ["new_template"]  # type: ignore[arg-type]
    stored.update(
        sha=t.content_sha256(face), manifest=face.model_dump(mode="json")["field_manifest"]
    )
    assert await t._changes(object(), face) == []  # type: ignore[arg-type]
    assert face.field_manifest is not None
    moved = [f.model_dump(mode="json") for f in face.field_manifest.fields]
    moved[1] = {**moved[1], "label": "F Total assets (see instructions)"}
    assert await t._changes(object(), _face(fields=moved)) == ["content_changed", "changed:f"]  # type: ignore[arg-type]


def test_the_manifest_diff() -> None:
    old = _face().model_dump(mode="json")["field_manifest"]
    face = _face()
    assert face.field_manifest is not None
    fields = [f.model_dump(mode="json") for f in face.field_manifest.fields][:2]
    fields.append({**fields[1], "key": "g", "label": "G Check applicable boxes"})
    new = _face(fields=fields).field_manifest
    assert new is not None
    assert t.manifest_diff(old, new) == ["added:g", "removed:k_1"]
