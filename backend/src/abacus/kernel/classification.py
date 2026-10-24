"""Data classification tags (ADR-031). TASK-005 design §6.

Every Pydantic model field carries one tag. Logging, error tracking, exports and the AI gateway
read the same tag from the field's JSON schema extra (`{"cls": <level>}`, as ADR-031 shows). Apply
it with `Annotated`, which keeps each field's own type and required-ness for the type checker:

    class EvidenceVersionOut(BaseModel):
        id: Annotated[UUID, classified("confidential")]
        extracted: Annotated[dict[str, object], classified("restricted")]

Three optional flags say what a Restricted value is (ADR-167 §1; Q-02-T32): `tri` (tax return
information), `phi` (health information) and `pii_kind` (the kind of personal identifier). Any
flag forces Restricted: a flag on another level raises when the model is defined, so at import.
The flags are written beside the level (`x-tri`, `x-phi`, `x-pii-kind`), so the OpenAPI document
carries them. Consumers ask the model (`tri_paths`, `phi_paths`, `pii_paths`), never a list of
field names, and mask through the one `mask(value, kind)`:

        tin: Annotated[str, classified("restricted", pii_kind="tin")]
        pii_paths(TaxpayerOut, "tin")      # ("tin",); nested models and containers included
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Literal, TypeAliasType, cast, get_args

from pydantic import BaseModel, Field
from pydantic.config import JsonDict
from pydantic.fields import FieldInfo

Classification = Literal["restricted", "confidential", "internal", "public"]
LEVELS: tuple[Classification, ...] = ("restricted", "confidential", "internal", "public")
KEY = "cls"


PiiKind = Literal["tin", "bank_account", "date_of_birth", "ip_pin"]
PII_KINDS: tuple[PiiKind, ...] = ("tin", "bank_account", "date_of_birth", "ip_pin")
TRI_KEY = "x-tri"
PHI_KEY = "x-phi"
PII_KIND_KEY = "x-pii-kind"


@dataclass(frozen=True)
class Flags:
    """What a Restricted value is, beyond its level (ADR-167 §1). Falsy when none is set."""

    tri: bool = False
    phi: bool = False
    pii_kind: PiiKind | None = None

    def __bool__(self) -> bool:
        return self.tri or self.phi or self.pii_kind is not None


def classified(
    level: Classification,
    *,
    tri: bool = False,
    phi: bool = False,
    pii_kind: PiiKind | None = None,
) -> FieldInfo:
    """Field metadata carrying the classification tag and its flags; use inside `Annotated[...]`.
    Any flag on a level other than `restricted` raises, so a model declaring one fails at import
    (Q-02 AC-19; there is no "Confidential TRI")."""
    if level not in LEVELS:
        raise ValueError(f"unknown classification {level!r}; valid: {', '.join(LEVELS)}")
    if pii_kind is not None and pii_kind not in PII_KINDS:
        raise ValueError(f"unknown pii_kind {pii_kind!r}; valid: {', '.join(PII_KINDS)}")
    flags = Flags(tri=tri, phi=phi, pii_kind=pii_kind)
    if flags and level != "restricted":
        raise ValueError(f"tri, phi and pii_kind force restricted; got {level!r} (ADR-167)")
    extra: JsonDict = {KEY: level}
    if tri:
        extra[TRI_KEY] = True
    if phi:
        extra[PHI_KEY] = True
    if pii_kind is not None:
        extra[PII_KIND_KEY] = pii_kind
    return cast(FieldInfo, Field(json_schema_extra=extra))


def level_of(field: FieldInfo) -> Classification | None:
    extra = field.json_schema_extra
    if isinstance(extra, dict):
        value = cast(dict[str, object], extra).get(KEY)
        for level in LEVELS:
            if value == level:
                return level
    return None


def unclassified_fields(model: type[BaseModel]) -> list[str]:
    """Names of fields on `model` without a valid classification tag."""
    return [name for name, field in model.model_fields.items() if level_of(field) is None]


def restricted_fields(model: type[BaseModel]) -> list[str]:
    return [name for name, field in model.model_fields.items() if level_of(field) == "restricted"]


def sensitive_paths(value: object, path: str = "") -> list[str]:
    """Dotted paths of Restricted or unclassified fields anywhere in `value`, nested included."""
    found: list[str] = []
    if isinstance(value, BaseModel):
        restricted = set(restricted_fields(type(value)))
        unclassified = set(unclassified_fields(type(value)))
        for field in type(value).model_fields:
            here = f"{path}.{field}" if path else field
            if field in restricted:
                found.append(here)
            elif (
                field in unclassified
            ):  # untagged means unknown, which must be treated as Restricted
                found.append(f"{here} (unclassified)")
            else:
                found += sensitive_paths(getattr(value, field), here)
    elif isinstance(value, Mapping):
        for key, item in cast(Mapping[object, object], value).items():
            found += sensitive_paths(item, f"{path}[{key!r}]")
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for index, item in enumerate(cast(Sequence[object], value)):
            found += sensitive_paths(item, f"{path}[{index}]")
    return found


# --- flags (ADR-167 §1) --------------------------------------------------------------------------


def _extra(field: FieldInfo) -> Mapping[str, object]:
    extra = field.json_schema_extra
    return cast(dict[str, object], extra) if isinstance(extra, dict) else {}


def flags_of(field: FieldInfo) -> Flags:
    """The field's flags as `classified()` wrote them (an unknown kind reads as none)."""
    extra = _extra(field)
    kind = extra.get(PII_KIND_KEY)
    return Flags(
        tri=extra.get(TRI_KEY) is True,
        phi=extra.get(PHI_KEY) is True,
        pii_kind=next((k for k in PII_KINDS if k == kind), None),
    )


def flag_errors(model: type[BaseModel]) -> list[str]:
    """Names of fields on `model` whose flags break ADR-167: set on a level other than
    `restricted`, or not as `classified()` writes them (the classification-tag check)."""
    errors: list[str] = []
    for name, field in model.model_fields.items():
        extra = _extra(field)
        keys = {TRI_KEY, PHI_KEY, PII_KIND_KEY} & extra.keys()
        if not keys:
            continue
        well_formed = (
            extra.get(TRI_KEY, True) is True
            and extra.get(PHI_KEY, True) is True
            and (PII_KIND_KEY not in extra or extra[PII_KIND_KEY] in PII_KINDS)
        )
        if level_of(field) != "restricted" or not well_formed:
            errors.append(name)
    return errors


def _models_in(annotation: object) -> list[type[BaseModel]]:
    """Pydantic models anywhere in a field's type: unions, optionals, lists, dicts, aliases."""
    if isinstance(annotation, TypeAliasType):
        return _models_in(annotation.__value__)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    found: list[type[BaseModel]] = []
    for arg in get_args(annotation):
        found += [m for m in _models_in(arg) if m not in found]
    return found


# A self-referential model (directly or through others) is unrolled this many levels on one path;
# a non-recursive model is walked to its full depth.
MAX_DEPTH = 5


@cache
def _flagged(model: type[BaseModel]) -> tuple[tuple[str, Flags], ...]:
    """Every flagged field's dotted path under `model`, in field order. Containers are
    transparent (`rows.tin` for a list of rows). A model may occur at most `MAX_DEPTH` times on
    one path, so a self-referential model lists `children.tin` down to `MAX_DEPTH` levels and
    the walk ends; a value nested deeper than that is still Restricted by its field's level."""

    def walk(
        current: type[BaseModel], prefix: str, seen: tuple[type[BaseModel], ...]
    ) -> list[tuple[str, Flags]]:
        out: list[tuple[str, Flags]] = []
        for name, field in current.model_fields.items():
            here = f"{prefix}.{name}" if prefix else name
            flags = flags_of(field)
            if flags:
                out.append((here, flags))
            for nested in _models_in(field.annotation):
                if seen.count(nested) < MAX_DEPTH:
                    out += walk(nested, here, (*seen, nested))
        return out

    return tuple(walk(model, "", (model,)))


def _model(model: type[BaseModel] | BaseModel) -> type[BaseModel]:
    return type(model) if isinstance(model, BaseModel) else model


def tri_paths(model: type[BaseModel] | BaseModel) -> tuple[str, ...]:
    """Dotted paths of the fields holding tax return information, nested models included."""
    return tuple(path for path, flags in _flagged(_model(model)) if flags.tri)


def phi_paths(model: type[BaseModel] | BaseModel) -> tuple[str, ...]:
    """Dotted paths of the fields holding health information, nested models included."""
    return tuple(path for path, flags in _flagged(_model(model)) if flags.phi)


def pii_paths(model: type[BaseModel] | BaseModel, kind: PiiKind) -> tuple[str, ...]:
    """Dotted paths of the fields holding a personal identifier of `kind`, nested included."""
    if kind not in PII_KINDS:
        raise ValueError(f"unknown pii_kind {kind!r}; valid: {', '.join(PII_KINDS)}")
    return tuple(path for path, flags in _flagged(_model(model)) if flags.pii_kind == kind)


# --- the one masking function (ADR-167 §1; Q-02 AC-20) -------------------------------------------

_DOB_MASK = "••/••/••••"
_IP_PIN_MASK = "••••••"


def mask(value: str, kind: PiiKind) -> str:
    """`value` as it may be displayed: a TIN keeps its last four digits (`•••-••-6789`,
    `tin_last4`, DEC-52); a bank number its last four characters; a date of birth and an
    IP PIN nothing at all, not even their length."""
    if kind == "tin":
        digits = [ch for ch in unicodedata.normalize("NFKC", value) if "0" <= ch <= "9"]
        return "•••-••-" + ("".join(digits[-4:]) if len(digits) >= 4 else "••••")
    if kind == "bank_account":
        kept = [ch for ch in unicodedata.normalize("NFKC", value) if ch.isascii() and ch.isalnum()]
        return "••••" + ("".join(kept[-4:]) if len(kept) >= 4 else "")
    if kind == "date_of_birth":
        return _DOB_MASK
    if kind == "ip_pin":
        return _IP_PIN_MASK
    raise ValueError(f"unknown pii_kind {kind!r}; valid: {', '.join(PII_KINDS)}")
