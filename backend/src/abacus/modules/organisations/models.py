"""Clients and client entities (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    name: Mapped[str]
    created_at: Mapped[datetime]


class ClientEntity(Base):
    __tablename__ = "client_entities"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    client_id: Mapped[UUID]
    name: Mapped[str]
    created_at: Mapped[datetime]
