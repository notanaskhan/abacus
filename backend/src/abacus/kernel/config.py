"""Typed settings from the environment (prefix `ABACUS_`). TASK-005 design §8.

Local and test defaults point at `docker compose`. Outside local and test, every connection setting
must be set explicitly, or startup fails: production can never run on a local default.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal, Self, cast

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from abacus.kernel.classification import classified

Environment = Literal["local", "test", "staging", "production"]
_LOCAL_DB = "postgresql+asyncpg://abacus_app:abacusapp@127.0.0.1:55432/abacus"
_LOCAL_MIGRATIONS_DB = "postgresql+asyncpg://abacus_owner:abacusowner@127.0.0.1:55432/abacus"
_CONNECTIONS = ("database_url", "migrations_database_url", "s3_endpoint_url", "temporal_target")
_LOCAL_DEFAULTS: dict[str, object] = {
    "database_url": _LOCAL_DB,
    "migrations_database_url": _LOCAL_MIGRATIONS_DB,
    "s3_endpoint_url": "http://127.0.0.1:7070",
    "s3_access_key": "abacus",
    "s3_secret_key": "abacuslocal",
    "temporal_target": "127.0.0.1:7233",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ABACUS_", extra="forbid", frozen=True)

    environment: Annotated[Environment, classified("internal")] = "local"
    database_url: Annotated[SecretStr | None, classified("restricted")] = None
    migrations_database_url: Annotated[SecretStr | None, classified("restricted")] = None
    database_statement_timeout_ms: Annotated[int, classified("internal")] = 30_000
    s3_endpoint_url: Annotated[str | None, classified("internal")] = None
    s3_access_key: Annotated[SecretStr | None, classified("restricted")] = None
    s3_secret_key: Annotated[SecretStr | None, classified("restricted")] = None
    s3_region: Annotated[str, classified("internal")] = "us-east-1"
    temporal_target: Annotated[str | None, classified("internal")] = None

    @model_validator(mode="before")
    @classmethod
    def _local_defaults(cls, data: object) -> object:
        """Local and test only: fill unset connection settings with the compose stack's values."""
        if not isinstance(data, dict):
            return data
        values = dict(cast(dict[str, object], data))
        if values.get("environment", "local") in ("local", "test"):
            for name, value in _LOCAL_DEFAULTS.items():
                values.setdefault(name, value)
        return values

    @model_validator(mode="after")
    def _explicit_outside_local(self) -> Self:
        missing = [name for name in _CONNECTIONS if getattr(self, name) is None]
        if missing:
            raise ValueError(
                f"{', '.join(missing)} must be set explicitly in environment {self.environment!r}"
            )
        return self


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
