"""Shared helpers for the Q-01 acceptance tests: a KMS stand-in that behaves the way the service is
documented to, a valid staging environment, and an in-process clamd.

Everything here is fake and obviously so: account 111111111111, no real ARN, no real key.
"""

from __future__ import annotations

import os
import socket
import struct
import threading
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import boto3
import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI

from abacus.api import create_app
from abacus.kernel.config import settings

if TYPE_CHECKING:
    from types_boto3_kms import KMSClient
    from types_boto3_sesv2 import SESV2Client

FAKE_ACCOUNT = "111111111111"
FAKE_REGION = "us-east-2"
Json = dict[str, Any]  # JSON-shaped boto3 and ASGI payloads, untyped by their libraries
PLATFORM_ALIAS = "alias/abacus/platform"
TENANT_ALIAS_PREFIX = "alias/abacus/tenant/"


def kms_client() -> KMSClient:
    """A real botocore KMS client with throwaway credentials, for `botocore.stub.Stubber`. Nothing
    is sent: a stubbed client never opens a connection."""
    return boto3.client(  # pyright: ignore[reportUnknownMemberType] -- only some stubs installed
        "kms",
        region_name=FAKE_REGION,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


def ses_client() -> SESV2Client:
    """The same for SES v2."""
    return boto3.client(  # pyright: ignore[reportUnknownMemberType] -- only some stubs installed
        "sesv2",
        region_name=FAKE_REGION,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


def client_error(code: str, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "fake failure"}}, operation)


class FakeKms:
    """An in-memory KMS. Like the real service it binds a ciphertext to the encryption context it
    was made with: Decrypt under a different context is refused with `InvalidCiphertextException`.

    `fail` maps an operation (`encrypt`, `decrypt`) to the error code to raise; `calls` records
    every call with its keyword arguments."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Json]] = []
        self.fail: dict[str, str] = {}
        self._blobs: dict[bytes, tuple[bytes, dict[str, str], str]] = {}

    def calls_to(self, operation: str) -> list[Json]:
        return [kwargs for name, kwargs in self.calls if name == operation]

    def encrypt(self, **kwargs: Any) -> Json:  # noqa: ANN401 - boto3 passes request fields as keywords
        self.calls.append(("encrypt", kwargs))
        if "encrypt" in self.fail:
            raise client_error(self.fail["encrypt"], "Encrypt")
        blob = uuid.uuid4().bytes + os.urandom(160)
        self._blobs[blob] = (
            bytes(kwargs["Plaintext"]),
            dict(kwargs.get("EncryptionContext", {})),
            str(kwargs["KeyId"]),
        )
        return {
            "CiphertextBlob": blob,
            "KeyId": f"arn:aws:kms:{FAKE_REGION}:{FAKE_ACCOUNT}:key/fake",
        }

    def decrypt(self, **kwargs: Any) -> Json:  # noqa: ANN401 - boto3 passes request fields as keywords
        self.calls.append(("decrypt", kwargs))
        if "decrypt" in self.fail:
            raise client_error(self.fail["decrypt"], "Decrypt")
        entry = self._blobs.get(bytes(kwargs["CiphertextBlob"]))
        if entry is None:
            raise client_error("InvalidCiphertextException", "Decrypt")
        plaintext, context, key_id = entry
        if dict(kwargs.get("EncryptionContext", {})) != context:
            raise client_error("InvalidCiphertextException", "Decrypt")
        if "KeyId" in kwargs and kwargs["KeyId"] != key_id:
            raise client_error("IncorrectKeyException", "Decrypt")
        return {"Plaintext": plaintext, "KeyId": key_id}


def as_kms(fake: FakeKms) -> Any:  # noqa: ANN401 - stands in for a KMSClient
    """The fake where a `KMSClient` is wanted."""
    return cast(Any, fake)  # the fake has the two methods the service calls


# --- a valid staging environment ----------------------------------------------------------------

KEYRING_V1 = "fake-payload-key-one-Zq8Xv2Lm9Wd4Rt7Bn3Hs"
KEYRING_V2 = "fake-payload-key-two-Mk5Pc1Yj6Ge8Fa2Ud9Qt"

STAGING: Mapping[str, str] = {
    "ABACUS_ENVIRONMENT": "staging",
    "ABACUS_DATABASE_URL": "postgresql+asyncpg://app@db.example.test:5432/abacus",
    "ABACUS_MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://owner@db.example.test:5432/abacus",
    "ABACUS_RELAY_DATABASE_URL": "postgresql+asyncpg://relay@db.example.test:5432/abacus",
    "ABACUS_IDENTITY_DATABASE_URL": "postgresql+asyncpg://identity@db.example.test:5432/abacus",
    "ABACUS_IDENTITY_ISSUER": "https://idp.example.test",
    "ABACUS_IDENTITY_AUDIENCE": "abacus-api",
    "ABACUS_IDENTITY_JWKS": '{"keys": []}',
    "ABACUS_S3_ENDPOINT_URL": "https://s3.example.test",
    "ABACUS_S3_ACCESS_KEY": "access",
    "ABACUS_S3_SECRET_KEY": "secret",
    "ABACUS_EVIDENCE_BUCKET": "evidence-bucket",
    "ABACUS_TEMPORAL_TARGET": "temporal.example.test:7233",
    "ABACUS_TEMPORAL_TLS": "true",
    "ABACUS_TEMPORAL_API_KEY": "test-temporal-api-key",
    "ABACUS_TRUSTED_HOSTS": "api.example.test",
    "ABACUS_KMS_PLATFORM_KEY_ALIAS": PLATFORM_ALIAS,
    "ABACUS_TEMPORAL_PAYLOAD_KEYS": f'{{"v1": "{KEYRING_V1}"}}',
    "ABACUS_TEMPORAL_PAYLOAD_CURRENT": "v1",
    "ABACUS_SCANNER_ENDPOINT": "scanner.abacus.internal:3310",
    "ABACUS_SES_CONFIGURATION_SET": "abacus-staging",
    "ABACUS_SES_FROM_ADDRESS": "notifications@mail.example.test",
}


def use_environment(
    monkeypatch: pytest.MonkeyPatch,
    base: Mapping[str, str],
    *,
    without: tuple[str, ...] = (),
    **overrides: str,
) -> None:
    """Set the process environment to `base`, minus `without`, plus `overrides`, and drop the
    cached settings."""
    values = {**base, **overrides}
    for name in without:
        values.pop(name, None)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    settings.cache_clear()


def use_staging(
    monkeypatch: pytest.MonkeyPatch, *, without: tuple[str, ...] = (), **overrides: str
) -> None:
    use_environment(monkeypatch, STAGING, without=without, **overrides)


_APPS: dict[tuple[tuple[str, str], ...], FastAPI] = {}


def cached_app(environment: Mapping[str, str]) -> FastAPI:
    """`create_app()` under exactly `environment`, built once per distinct environment: building
    the application is the slow part of an edge test, and the edge middleware is fixed when the
    app is built."""
    key = tuple(sorted(environment.items()))
    if key not in _APPS:
        with pytest.MonkeyPatch.context() as patch:
            for name in list(os.environ):
                if name.startswith("ABACUS_"):
                    patch.delenv(name)
            for name, value in environment.items():
                patch.setenv(name, value)
            settings.cache_clear()
            _APPS[key] = create_app()
        settings.cache_clear()
    return _APPS[key]


def override(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    """Set one more variable and drop the cached settings."""
    monkeypatch.setenv(name, value)
    settings.cache_clear()


def fails(call: Callable[[], Any]) -> BaseException:  # the return value is irrelevant
    """The exception `call` raises. The test fails if it returns."""
    try:
        call()
    except Exception as exc:  # the caller asserts on it
        return exc
    raise AssertionError("expected the call to fail, but it returned")


async def afails(call: Callable[[], Awaitable[Any]]) -> BaseException:  # result unused
    """The exception the awaited `call` raises. The test fails if it returns."""
    try:
        await call()
    except Exception as exc:  # the caller asserts on it
        return exc
    raise AssertionError("expected the call to fail, but it returned")


# --- an in-process clamd ------------------------------------------------------------------------

EICAR = (
    rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$"
    + rb"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"  # the standard antivirus test string
)
STREAM_MAX_LENGTH = 60 * 1024 * 1024  # clamd's StreamMaxLength 60M


@dataclass
class ClamdSeen:
    connections: int = 0
    commands: list[bytes] = field(default_factory=lambda: [])
    streamed: list[bytes] = field(default_factory=lambda: [])


class FakeClamd:
    """A loopback clamd that speaks the protocol: a `zINSTREAM`/`nINSTREAM` command followed by
    length-prefixed chunks and a zero-length terminator, answered `stream: OK`, or
    `stream: <name> FOUND` when the whole stream is the EICAR file, or the `StreamMaxLength`
    error past 60 MiB. `PING` is answered `PONG`.

    `mode` makes it misbehave: `reply` sends `reply` verbatim instead of a verdict, `silent`
    reads the request and never answers, `deaf` accepts and never reads, `close` drops the
    connection after reading the command. `ping_reply` is what `PING` is answered with."""

    def __init__(
        self, *, mode: str = "normal", reply: bytes = b"", ping_reply: bytes = b"PONG\0"
    ) -> None:
        self.mode = mode
        self.reply = reply
        self.ping_reply = ping_reply
        self.seen = ClamdSeen()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(8)
        self._server.settimeout(0.2)
        self._stop = threading.Event()
        self._accept = threading.Thread(target=self._serve, daemon=True)
        self._accept.start()

    @property
    def endpoint(self) -> str:
        return f"127.0.0.1:{self._server.getsockname()[1]}"

    def close(self) -> None:
        self._stop.set()
        self._accept.join(timeout=2)
        self._server.close()

    def __enter__(self) -> FakeClamd:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            self.seen.connections += 1
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    @staticmethod
    def _read(conn: socket.socket, count: int) -> bytes:
        data = b""
        while len(data) < count:
            part = conn.recv(count - len(data))
            if not part:
                raise ConnectionError("peer closed")
            data += part
        return data

    def _command(self, conn: socket.socket) -> bytes:
        first = self._read(conn, 1)
        if first not in (b"z", b"n"):
            raise ConnectionError("not a clamd command")
        terminator = b"\0" if first == b"z" else b"\n"
        command = b""
        while True:
            byte = self._read(conn, 1)
            if byte == terminator:
                return command
            command += byte

    def _handle(self, conn: socket.socket) -> None:
        with conn:
            conn.settimeout(10)
            try:
                if self.mode == "deaf":
                    self._stop.wait(5)
                    return
                command = self._command(conn)
                self.seen.commands.append(command)
                if command == b"PING":
                    conn.sendall(self.ping_reply)
                    return
                if command != b"INSTREAM":
                    conn.sendall(b"UNKNOWN COMMAND\0")
                    return
                if self.mode == "close":
                    return
                total = bytearray()
                while True:
                    (length,) = struct.unpack(">I", self._read(conn, 4))
                    if length == 0:
                        break
                    total += self._read(conn, length)
                    if len(total) > STREAM_MAX_LENGTH:
                        conn.sendall(b"INSTREAM size limit exceeded. ERROR\0")
                        return
                self.seen.streamed.append(bytes(total))
                if self.mode == "silent":
                    self._stop.wait(5)
                    return
                if self.mode == "reply":
                    conn.sendall(self.reply)
                    return
                if bytes(total) == EICAR:
                    conn.sendall(b"stream: Eicar-Test-Signature FOUND\0")
                else:
                    conn.sendall(b"stream: OK\0")
            except (ConnectionError, OSError, TimeoutError):
                return


def closed_endpoint() -> str:
    """A loopback `host:port` nothing listens on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"127.0.0.1:{port}"
