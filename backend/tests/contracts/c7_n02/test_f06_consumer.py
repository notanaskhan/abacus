# ac-test-author: ayushkbhatia
"""F-06-T09: the T16 signing kit's consumer contract, in the provider's CI. The kit's mapper
(`apps/web/src/domain/signing/envelope-vm.ts`, `toEnvelopeVM`) reads these C7 fields; a rename,
a type change or a removed value of any of them fails here before the signing kit breaks
(`docs/contracts/c7-envelopes.md`). The TypeScript half is `envelope-vm.test.ts`, typed by the
generated client.

C5's part is the portal scope the page and session routes run under: a portal member's route,
never a firm one, so a page image is only ever served inside the signer's scope (INV-4).
"""

from __future__ import annotations

import json
from typing import cast

import pytest

from abacus.api.export_openapi import document

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])

# (schema, field) -> what the mapper relies on: a JSON type, or the exact enum values it maps.
READS: dict[tuple[str, str], object] = {
    ("PortalEnvelopeView", "row"): "ref:PortalEnvelopeRow",
    ("PortalEnvelopeView", "documents"): "array",
    ("PortalEnvelopeView", "my_fields"): "array",
    ("PortalEnvelopeView", "signers_signed"): "integer",
    ("PortalEnvelopeView", "signers_total"): "integer",
    ("PortalEnvelopeView", "paper_form_follows"): "boolean",
    ("PortalEnvelopeView", "signing_session"): "ref:SigningSessionOut",
    ("PortalEnvelopeView", "outcome"): {"signed", "declined", "abandoned"},
    ("PortalEnvelopeRow", "id"): "string",
    ("PortalEnvelopeRow", "title"): "string",
    ("PortalEnvelopeRow", "status"): "ref:EnvelopeStatus",
    ("PortalEnvelopeRow", "my_status"): "ref:EnvelopeSignerStatus",
    ("EnvelopeDocumentOut", "id"): "string",
    ("EnvelopeDocumentOut", "order"): "integer",
    ("EnvelopeDocumentOut", "title"): "string",
    ("EnvelopeDocumentOut", "page_count"): "integer",
    ("FieldOut", "id"): "string",
    ("FieldOut", "document_id"): "string",
    ("FieldOut", "page"): "integer",
    ("FieldOut", "x"): "number",
    ("FieldOut", "y"): "number",
    ("FieldOut", "w"): "number",
    ("FieldOut", "h"): "number",
    ("FieldOut", "kind"): {"signature", "pin", "date", "initial", "title_prefill"},
    ("SigningSessionOut", "url"): "string",
    ("SigningSessionOut", "presentation"): {"iframe", "redirect"},
    ("SigningSessionOut", "expires_at"): "string",
    ("SignerDeclineIn", "reason"): {
        "have_questions",
        "something_wrong",
        "someone_else_should_sign",
        "other",
    },
}
# The status words the kit's registry renders (C2): every C7 value must be one it knows.
ENUMS: dict[str, set[str]] = {
    "EnvelopeStatus": {
        "draft",
        "sent",
        "viewed",
        "partially_signed",
        "completed",
        "declined",
        "expired",
        "voided",
    },
    "EnvelopeSignerStatus": {
        "pending",
        "viewed",
        "verified",
        "signed",
        "declined",
        "verification_failed",
    },
}
# The portal routes the kit's container calls, and the scope they run under.
ROUTES = {
    ("get", "/v1/portal/envelopes/{envelope_id}"),
    ("get", "/v1/portal/envelopes/{envelope_id}/documents/{document_id}/pages/{page_no}"),
    ("post", "/v1/portal/envelopes/{envelope_id}/signing-session"),
    ("get", "/v1/portal/envelopes/{envelope_id}/signing-session/{session_id}/return"),
    ("post", "/v1/portal/envelopes/{envelope_id}/decline"),
    ("get", "/v1/portal/envelopes/{envelope_id}/download"),
}


def _field(schema: str, name: str) -> Json:
    props = cast(dict[str, Json], SCHEMAS[schema]["properties"])
    assert name in props, f"C7 dropped {schema}.{name}, which the signing kit maps"
    return props[name]


def _shape(node: Json) -> tuple[set[str], set[str], set[str]]:
    """(json types, $ref names, enum values) of a property, through anyOf for nullables."""
    types: set[str] = set()
    refs: set[str] = set()
    enum: set[str] = set()
    for part in cast(list[Json], node.get("anyOf", [node])):
        if "$ref" in part:
            refs.add(str(part["$ref"]).rsplit("/", 1)[1])
        if "type" in part:
            types.add(str(part["type"]))
        enum |= {str(v) for v in cast(list[object], part.get("enum", []))}
        if "const" in part:
            enum.add(str(part["const"]))
    return types, refs, enum


@pytest.mark.parametrize(("schema", "name"), sorted(READS))
def test_f06t09_each_mapped_field_keeps_its_shape(schema: str, name: str) -> None:
    types, refs, enum = _shape(_field(schema, name))
    want = READS[(schema, name)]
    if isinstance(want, set):
        values = cast(set[str], want)
        assert enum == values, f"{schema}.{name} values changed: the kit maps {sorted(values)}"
    elif isinstance(want, str) and want.startswith("ref:"):
        assert want[4:] in refs, f"{schema}.{name} is no longer {want[4:]}"
    else:
        assert want in types, f"{schema}.{name} is no longer {want}"


@pytest.mark.parametrize("name", sorted(ENUMS))
def test_f06t09_status_values_are_the_ones_the_kit_words(name: str) -> None:
    assert set(cast(list[str], SCHEMAS[name]["enum"])) == ENUMS[name]


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_f06t09_the_container_routes_exist_as_portal_routes(method: str, path: str) -> None:
    assert path in PATHS and method in PATHS[path], f"C7 dropped {method.upper()} {path}"
    action = str(PATHS[path][method].get("x-abacus-action", ""))
    assert action.startswith(("portal_envelopes.", "portal_envelope.", "envelope_signer.")), action
