"""The ORM base every module's models derive from (ADR-012). PROTECTED. TASK-008.

Tables are created by hand-written migrations, never by `metadata.create_all`. The naming
convention only keeps names predictable when the ORM emits them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "%(table_name)s_%(column_0_name)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Every timestamp column is timestamptz: Python datetimes map to it, aware, in UTC.
    type_annotation_map: ClassVar[dict[Any, Any]] = {  # Any: SQLAlchemy's own annotation type
        datetime: DateTime(timezone=True)
    }
