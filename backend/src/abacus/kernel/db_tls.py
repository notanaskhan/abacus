"""Database TLS: verify the server's certificate whenever TLS is in use (G-09; ASVS 1.9.2, 9.2.3).
PROTECTED.

Used by `kernel.db` (every engine), `kernel.config` (validation) and the migration environment.
asyncpg's default (`prefer`) uses TLS when the server offers it but checks no certificate, so a
machine in the path could pose as the database. Here every connection is either plain (local and
test only, when nothing asks for TLS) or TLS with the certificate chain and the host name checked
(`verify-full`):

- Outside local and test, TLS is always on, and a DSN that turns it off (`sslmode=disable`) is
  refused by settings validation and again here.
- A DSN that asks for any TLS mode (`sslmode` or asyncpg's `ssl`: `allow`, `prefer`, `require`,
  `verify-ca`, `verify-full`, `true`) gets `verify-full`: a weaker mode is never honoured.
- `database_ca_file` names the CA bundle to trust (for RDS, the AWS global bundle); unset, the
  system trust store is used. Setting it turns TLS on in local and test too.

The DSN's own `ssl`/`sslmode` parameters are removed before the URL reaches the driver, so they
can't override the context.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import Final, Literal

from sqlalchemy.engine import make_url

_PARAMS: Final = ("ssl", "sslmode")
_OFF: Final = frozenset({"disable", "false", "off", "0", "no"})


class InsecureDatabaseUrl(ValueError):
    """A DSN asks for a plain connection where TLS is required (outside local and test)."""


@dataclass(frozen=True)
class DatabaseTls:
    url: str
    # False: a plain connection (local and test only); otherwise the verifying context.
    ssl: ssl.SSLContext | Literal[False]


def requested_mode(url: str) -> str | None:
    """The TLS mode the DSN asks for, lower-cased (`sslmode` wins over `ssl`), or None."""
    query = make_url(url).query
    for name in ("sslmode", "ssl"):
        value = query.get(name)
        if isinstance(value, tuple):
            value = value[-1] if value else None
        if value is not None:
            return str(value).strip().lower()
    return None


def turns_tls_off(url: str) -> bool:
    return requested_mode(url) in _OFF


def verifying_context(ca_file: str | None) -> ssl.SSLContext:
    """TLS 1.2 or later, the chain checked against `ca_file` (or the system store) and the
    certificate's name checked against the host (`verify-full`)."""
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_file)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def database_tls(url: str, *, local: bool, ca_file: str | None) -> DatabaseTls:
    """The URL to hand the driver and how to connect: plain only on the local stack (local,
    test, evaluation) when nothing asks for TLS or the DSN turns it off; else `verify-full`."""
    parsed = make_url(url)
    stripped = parsed.difference_update_query(_PARAMS).render_as_string(hide_password=False)
    mode = requested_mode(url)
    if mode in _OFF:
        if not local:
            raise InsecureDatabaseUrl("database connections need TLS outside local and test")
        return DatabaseTls(stripped, False)
    if local and mode is None and ca_file is None:
        return DatabaseTls(stripped, False)
    return DatabaseTls(stripped, verifying_context(ca_file))
