"""Q-04-T035 (TASK-7800): the firm exit rehearsed on a rehearsal tenant, end to end.

AC: the rehearsal tenant exits end to end with a dual-approved export, verified checksums and a
certificate naming both dates (`docs/runbooks/firm-exit.md`).

The rehearsal tenant is a synthetic firm (Q-02-T47's fixture: a security admin requests, a
partner approves). Its firm export is built and downloaded through the real routes, written to
disk as the firm would receive it, verified with `abacus_tools.firm_exit verify` against the
export row's digests, and the certificate is written from the report and the key custodian's
`ScheduleKeyDeletion` answer. Local runs use the in-memory key service (ADR-156: nothing here may
delete a KMS key), so the custodian's answer is the shape `aws kms schedule-key-deletion` returns.
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from abacus_tools import firm_exit

from .test_q02t47_firm_export_packages import (  # the same synthetic firm and build
    Firm,
    _ready_archive,  # pyright: ignore[reportPrivateUsage]
    firm,
    raw,
    wired,
)

__all__ = ["firm", "raw", "wired"]  # fixtures shared with Q-02-T47


async def test_ac_the_rehearsal_tenant_exits_end_to_end(firm: Firm, tmp_path: Path) -> None:
    row, archive = await _ready_archive(firm)
    assert row.requested_by != row.decided_by  # dual approval: two people, enforced by the DB
    received = tmp_path / "firm-export.zip"
    received.write_bytes(archive)

    report = firm_exit.verify(
        received,
        tmp_path / "unpacked",
        bundle_sha256=row.bundle_sha256,
        manifest_sha256=row.manifest_sha256,
    )
    assert report.ok, report.problems
    assert report.export_id == str(row.id)
    assert (report.requested_by, report.approved_by) == (
        str(firm.admin.user_id),
        str(firm.partner.user_id),
    )
    assert {p["engagement_id"] for p in report.packages} == {str(firm.packaged)}
    assert all(p["ok"] for p in report.packages)

    built = datetime.fromisoformat(str(report.built_at).replace("Z", "+00:00"))
    deletion = {
        "KeyId": f"arn:aws:kms:us-east-2:000000000000:key/mrk-{firm.tenant.hex}",
        "KeyState": "PendingDeletion",
        "PendingWindowInDays": 30,
        "DeletionDate": (built + timedelta(days=30)).isoformat(),
    }
    (tmp_path / "report.json").write_text(json.dumps(report.as_json()))
    (tmp_path / "kms.json").write_text(json.dumps(deletion))
    out = tmp_path / "certificate.json"
    assert (
        firm_exit.main(
            [
                "certificate",
                "--verification",
                str(tmp_path / "report.json"),
                "--key-deletion",
                str(tmp_path / "kms.json"),
                "--firm",
                "PF-X1",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    certificate = json.loads(out.read_text())
    assert certificate["tenant_id"] == str(firm.tenant)
    assert certificate["export"]["archive_sha256"] == row.bundle_sha256
    dates = certificate["dates"]
    assert datetime.fromisoformat(dates["export_verified"].replace("Z", "+00:00")) == built
    assert datetime.fromisoformat(dates["key_deleted"].replace("Z", "+00:00")) == built.astimezone(
        UTC
    ) + timedelta(days=30)


async def test_a_changed_archive_cannot_earn_a_certificate(firm: Firm, tmp_path: Path) -> None:
    row, archive = await _ready_archive(firm)
    received = tmp_path / "firm-export.zip"
    received.write_bytes(archive[:-1] + bytes([archive[-1] ^ 1]))
    try:
        report = firm_exit.verify(
            received,
            tmp_path / "unpacked",
            bundle_sha256=row.bundle_sha256,
            manifest_sha256=row.manifest_sha256,
        )
    except zipfile.BadZipFile:
        return  # refused before unpacking: no report, so no certificate
    assert not report.ok
    with pytest.raises(firm_exit.ExitRefused, match="did not verify"):
        firm_exit.certificate(
            report.as_json(),
            {"KeyId": "k", "KeyState": "PendingDeletion", "DeletionDate": "2099-01-01"},
            firm="PF-X1",
            issued_at=datetime.now(UTC),
        )
