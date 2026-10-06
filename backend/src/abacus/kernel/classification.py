"""Data classification tags (ADR-031). TASK-005 design §6.

Every Pydantic model field carries one tag. Logging, error tracking, exports and the AI gateway
read the same tag from the field's JSON schema extra (`{"cls": <level>}`, as ADR-031 shows). Apply
it with `Annotated`, which keeps each field's own type and required-ness for the type checker:

    class EvidenceVersionOut(BaseModel):
        id: Annotated[UUID, classified("confidential")]
        extracted: Annotated[dict[str, object], classified("restricted")]
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, cast

from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

Classification = Literal["restricted", "confidential", "internal", "public"]
LEVELS: tuple[Classification, ...] = ("restricted", "confidential", "internal", "public")
KEY = "cls"


def classified(level: Classification) -> FieldInfo:
    """Field metadata carrying the classification tag; use inside `Annotated[...]`."""
    if level not in LEVELS:
        raise ValueError(f"unknown classification {level!r}; valid: {', '.join(LEVELS)}")
    return cast(FieldInfo, Field(json_schema_extra={KEY: level}))


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
