"""Q-04-T019: an export package unpacks into a blank folder safely and verifies (firm rollback).

Acceptance: the canary rollback completes inside 60 minutes with checksums verified. The check
is the package README's (`shasum -a 256 -c` on both checksum files) plus what a firm's folder
needs: nothing written outside it, nothing unlisted, the manifest agreeing with the checksums.
"""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path

import pytest

from abacus_tools import package_check as pc

FILES = {"README.txt": b"readme", "index.csv": b"a,b\n", "evidence/Cash/bank.pdf": b"%PDF-1.7 x"}


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _package(
    path: Path, files: dict[str, bytes] = FILES, *, extra: dict[str, bytes] | None = None
) -> Path:
    manifest = json.dumps(
        {"files": [{"path": p, "sha256": _sha(b)} for p, b in sorted(files.items())]},
        sort_keys=True,
    ).encode()
    listed = {**files, "manifest.json": manifest}
    checksums = "".join(f"{_sha(b)}  {p}\n" for p, b in sorted(listed.items())).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in {**listed, **(extra or {})}.items():
            archive.writestr(name, body)
        archive.writestr("manifest.sha256", f"{_sha(manifest)}  manifest.json\n")
        archive.writestr("checksums.sha256", checksums)
    return path


def test_a_good_package_unpacks_into_a_new_folder_and_verifies(tmp_path: Path) -> None:
    folder = tmp_path / "workpapers"
    pc.unpack(_package(tmp_path / "p.zip"), folder)
    result = pc.verify(folder)
    assert result.ok, result.as_json()
    assert result.checked == {"manifest.sha256": 1, "checksums.sha256": 4}


def test_a_changed_file_fails_its_checksum(tmp_path: Path) -> None:
    folder = tmp_path / "w"
    pc.unpack(_package(tmp_path / "p.zip"), folder)
    (folder / "index.csv").write_bytes(b"a,b,c\n")
    result = pc.verify(folder)
    assert not result.ok and result.mismatched == ["index.csv"]


def test_a_file_the_checksums_do_not_name_is_unlisted(tmp_path: Path) -> None:
    folder = tmp_path / "w"
    pc.unpack(_package(tmp_path / "p.zip", extra={"stray.txt": b"x"}), folder)
    assert pc.verify(folder).unlisted == ["stray.txt"]


def test_the_manifest_must_agree_with_the_checksums(tmp_path: Path) -> None:
    folder = tmp_path / "w"
    pc.unpack(_package(tmp_path / "p.zip"), folder)
    body = json.loads((folder / "manifest.json").read_text())
    body["files"][0]["sha256"] = "0" * 64
    (folder / "manifest.json").write_text(json.dumps(body))
    result = pc.verify(folder)
    assert "README.txt" in result.manifest_disagrees and not result.ok


def test_a_missing_checksum_file_is_not_ok(tmp_path: Path) -> None:
    folder = tmp_path / "w"
    pc.unpack(_package(tmp_path / "p.zip"), folder)
    (folder / "manifest.sha256").unlink()
    result = pc.verify(folder)
    assert "manifest.sha256" in result.missing and not result.ok


@pytest.mark.parametrize(
    "name", ["../escape.txt", "/etc/escape", "evidence/../../x", "C:/x", "a\\b"]
)
def test_an_entry_that_leaves_the_folder_is_refused_before_anything_is_written(
    tmp_path: Path, name: str
) -> None:
    package = tmp_path / "evil.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("ok.txt", b"ok")
        archive.writestr(name, b"x")
    with pytest.raises(pc.PackageRefused):
        pc.unpack(package, tmp_path / "w")
    assert not (tmp_path / "w").exists() and not (tmp_path / "escape.txt").exists()


def test_a_symlink_entry_is_refused(tmp_path: Path) -> None:
    package = tmp_path / "link.zip"
    info = zipfile.ZipInfo("link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(info, "/etc/passwd")
    with pytest.raises(pc.PackageRefused, match="symbolic link"):
        pc.unpack(package, tmp_path / "w")


def test_an_existing_folder_and_an_oversized_package_are_refused(tmp_path: Path) -> None:
    package = _package(tmp_path / "p.zip")
    (tmp_path / "taken").mkdir()
    with pytest.raises(pc.PackageRefused, match="blank folder"):
        pc.unpack(package, tmp_path / "taken")
    with pytest.raises(pc.PackageRefused, match="bytes unpacked"):
        pc.unpack(package, tmp_path / "w", max_bytes=10)


def test_the_command_exits_by_outcome(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    package = _package(tmp_path / "p.zip")
    assert pc.main([str(package), "--into", str(tmp_path / "a")]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert pc.main([str(package), "--into", str(tmp_path / "a")]) == 2  # the folder exists now
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    assert pc.main([str(bad), "--into", str(tmp_path / "b")]) == 2
