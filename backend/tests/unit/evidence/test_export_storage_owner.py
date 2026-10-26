"""DEC-454 (security review): the exports store names the account that must own the bucket.

With `exports_bucket_owner` set, every exports call carries `ExpectedBucketOwner`, so a bucket of
the same name in another account is refused by S3; unset, nothing extra is sent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from abacus.kernel.config import Settings
from abacus.modules.evidence import export_storage

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

TENANT = UUID(int=1)
EXPORT = UUID(int=2)


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_objects_v2(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("list", kwargs))
        prefix = export_storage.export_prefix(TENANT, EXPORT)
        return {"Contents": [{"Key": f"{prefix}segment-0000"}, {"Key": f"{prefix}segment-0001"}]}

    def delete_object(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("delete", kwargs))
        return {}


@pytest.mark.parametrize("owner", ["000000000000", None])
async def test_every_call_carries_the_expected_owner_when_one_is_set(owner: str | None) -> None:
    client = Recorder()
    s3 = cast("S3Client", client)  # a recorder standing in for boto3's client
    exports = export_storage._Exports  # pyright: ignore[reportPrivateUsage] -- the store's own target
    drop = export_storage._drop_from  # pyright: ignore[reportPrivateUsage] -- no crypto needed
    target = exports(s3, "abacus-test-exports", owner)
    await drop(target, TENANT, EXPORT, 1)
    assert [name for name, _ in client.calls] == ["list", "delete"]
    for _, kwargs in client.calls:
        assert kwargs.get("ExpectedBucketOwner") == owner


def test_the_owner_setting_is_an_account_number_or_nothing() -> None:
    assert Settings(exports_bucket_owner="000000000000").exports_bucket_owner == "000000000000"
    assert Settings().exports_bucket_owner is None
    with pytest.raises(ValidationError):
        Settings(exports_bucket_owner="not-an-account")
