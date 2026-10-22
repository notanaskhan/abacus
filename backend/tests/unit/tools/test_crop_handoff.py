"""The visual-parity crop tool and baseline fetch (F-05-T16; chapter 04 §9.3)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from abacus_tools.parity import baselines, crop_handoff
from abacus_tools.parity.crop_handoff import (
    WINDOW_CROP,
    Entry,
    Json,
    ManifestError,
    SourceError,
    baseline_file,
    crop_all,
    crop_entry,
    load_manifest,
    parse_entry,
    pin,
    read_version,
)

GOOD: Json = {
    "source": "kit-handoffs/C-06 x/screenshots/a.png",
    "sha256": "a" * 64,
    "crop": [2, 3, 6, 7],
    "tier": "A",
}


def _png(path: Path, size: tuple[int, int] = (10, 10), alpha: int = 255) -> str:
    """A PNG whose pixel (x, y) is (x*20, y*20, 7); returns its SHA-256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size)
    for x in range(size[0]):
        for y in range(size[1]):
            image.putpixel((x, y), (x * 20, y * 20, 7, alpha))
    image.save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _handoff(tmp_path: Path) -> tuple[Path, Entry]:
    root = tmp_path / "handoff"
    sha = _png(root / "kit-handoffs/C-06 x/screenshots/a.png")
    entry = parse_entry("c-06-tick.ms", {**GOOD, "sha256": sha})
    return root, entry


def _write_manifest(path: Path, entries: Json) -> Path:
    path.write_text(json.dumps({"schema": 1, "entries": entries}), encoding="utf-8")
    return path


# ---- The checked-in manifest ------------------------------------------------------------------


def test_the_checked_in_manifest_loads() -> None:
    entries = load_manifest()
    assert len(entries) >= 10
    assert {e.tier for e in entries} <= {"A", "B", "C", "D"}
    assert all(e.sha256 != "0" * 64 for e in entries), "pinned: run crop_handoff --pin"
    # F-04-T14 pins the screen index's hash after the version: `<version> sha256:<hex>`.
    assert read_version() == crop_handoff.VERSION_FILE.read_text(encoding="utf-8").split()[0]


def test_the_manifest_names_gallery_specimens_that_exist() -> None:
    index = (crop_handoff.REPO / "packages/ui/src/specimens/index.ts").read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid: "([a-z0-9-]+)"', index))
    # A screen baseline (P-01-T02) renders its screen route, not a gallery specimen.
    missing = {e.specimen for e in load_manifest() if e.page is None} - ids
    assert missing == set()


def test_a_recorded_deviation_is_never_silent() -> None:
    for entry in load_manifest():
        if entry.deviation is not None:
            assert len(entry.deviation) > 20, entry.key


# ---- Manifest validation ----------------------------------------------------------------------


def test_a_good_entry_parses() -> None:
    entry = parse_entry("c-06-tick.ms", GOOD)
    assert (entry.specimen, entry.crop, entry.tier, entry.locked) == (
        "c-06-tick",
        (2, 3, 6, 7),
        "A",
        False,
    )
    assert entry.deviation is None
    assert entry.selector is None


def test_the_window_alias_is_the_plans_crop() -> None:
    entry = parse_entry("tpl-01", {**GOOD, "crop": "window", "locked": True})
    assert entry.crop == WINDOW_CROP == (40, 40, 2840, 1760)
    assert entry.locked is True


@pytest.mark.parametrize(
    ("key", "patch", "message"),
    [
        ("Bad Key", {}, "a key is"),
        ("c-06.a.b", {}, "a key is"),
        ("k", {"source": "a.jpg"}, '"source"'),
        ("k", {"source": 3}, '"source"'),
        ("k", {"source": "/etc/a.png"}, "inside the handoff root"),
        ("k", {"source": "../a.png"}, "inside the handoff root"),
        ("k", {"sha256": "xyz"}, '"sha256"'),
        ("k", {"tier": "E"}, '"tier"'),
        ("k", {"selector": 4}, '"selector"'),
        ("k", {"deviation": " "}, '"deviation"'),
        ("k", {"crop": [1, 2, 3]}, '"crop"'),
        ("k", {"crop": [1, 2, 3, "4"]}, '"crop"'),
        ("k", {"crop": [1, 2, True, 4]}, '"crop"'),
        ("k", {"crop": "everything"}, '"crop"'),
        ("k", {"crop": [5, 0, 5, 9]}, "empty or negative"),
        ("k", {"crop": [-1, 0, 5, 9]}, "empty or negative"),
    ],
)
def test_a_malformed_entry_is_refused(key: str, patch: Json, message: str) -> None:
    with pytest.raises(ManifestError, match=message):
        parse_entry(key, {**GOOD, **patch})


@pytest.mark.parametrize(
    "document",
    [[], {"schema": 2, "entries": {"k": GOOD}}, {"schema": 1}, {"schema": 1, "entries": {}}],
)
def test_a_malformed_manifest_is_refused(tmp_path: Path, document: object) -> None:
    path = tmp_path / "m.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_a_version_is_one_token(tmp_path: Path) -> None:
    path = tmp_path / "HANDOFF_VERSION"
    path.write_text("2026-10-21\n", encoding="utf-8")
    assert read_version(path) == "2026-10-21"
    path.write_text("two words", encoding="utf-8")
    with pytest.raises(ManifestError, match="one token"):
        read_version(path)
    path.write_text("2026-10-21 sha256:" + "a" * 64 + "\n", encoding="utf-8")
    assert read_version(path) == "2026-10-21"


def test_baseline_files_have_no_dots_in_the_stem() -> None:
    assert baseline_file("c-06-tick.ms") == "c-06-tick-ms.png"
    assert baseline_file("tpl-01") == "tpl-01.png"


# ---- Cropping ---------------------------------------------------------------------------------


def test_the_crop_is_the_box_in_source_pixels(tmp_path: Path) -> None:
    root, entry = _handoff(tmp_path)
    region = crop_entry(root, entry)
    assert region.size == (4, 4)
    assert region.mode == "RGB"
    assert region.getpixel((0, 0)) == (40, 60, 7)
    assert region.getpixel((3, 3)) == (100, 120, 7)


def test_transparency_is_flattened_onto_white(tmp_path: Path) -> None:
    root = tmp_path / "handoff"
    sha = _png(root / GOOD["source"], alpha=0)
    entry = parse_entry("k", {**GOOD, "sha256": sha})
    assert crop_entry(root, entry).getpixel((1, 1)) == (255, 255, 255)


def test_a_missing_source_is_an_error(tmp_path: Path) -> None:
    _, entry = _handoff(tmp_path)
    with pytest.raises(SourceError, match="is not in the handoff"):
        crop_entry(tmp_path / "elsewhere", entry)


def test_a_changed_source_is_refused_unless_unverified(tmp_path: Path) -> None:
    root, entry = _handoff(tmp_path)
    _png(root / entry.source, size=(12, 12))
    with pytest.raises(SourceError, match="has changed since the manifest was pinned"):
        crop_entry(root, entry)
    assert crop_entry(root, entry, verify=False).size == (4, 4)


def test_a_crop_outside_the_source_is_an_error(tmp_path: Path) -> None:
    root, entry = _handoff(tmp_path)
    tall = parse_entry("k", {**GOOD, "sha256": entry.sha256, "crop": [0, 0, 11, 5]})
    with pytest.raises(SourceError, match="is outside"):
        crop_entry(root, tall)


def test_crop_all_writes_the_version_directory_and_an_index(tmp_path: Path) -> None:
    root, entry = _handoff(tmp_path)
    index = crop_all(root, tmp_path / "out", [entry], "v1")
    written = tmp_path / "out" / "v1" / "c-06-tick-ms.png"
    assert Image.open(written).size == (4, 4)
    on_disk = json.loads((tmp_path / "out" / "v1" / "index.json").read_text(encoding="utf-8"))
    assert on_disk == index
    item = index["entries"]["c-06-tick.ms"]
    assert item["sha256"] == hashlib.sha256(written.read_bytes()).hexdigest()
    assert (item["file"], item["size"], item["tier"]) == ("c-06-tick-ms.png", [4, 4], "A")
    assert item["source_sha256"] == entry.sha256


def test_crop_all_can_skip_sources_that_are_not_on_disk(tmp_path: Path) -> None:
    root, entry = _handoff(tmp_path)
    absent = parse_entry("c-06-tick.cf", {**GOOD, "source": "kit-handoffs/none.png"})
    index = crop_all(root, tmp_path / "out", [entry, absent], "v1", skip_missing=True)
    assert list(index["entries"]) == ["c-06-tick.ms"]
    with pytest.raises(SourceError):
        crop_all(root, tmp_path / "out", [entry, absent], "v1")


def test_pin_rewrites_hashes_from_the_handoff(tmp_path: Path) -> None:
    root, entry = _handoff(tmp_path)
    manifest = _write_manifest(tmp_path / "m.json", {"c-06-tick.ms": {**GOOD, "sha256": "0" * 64}})
    assert pin(root, manifest) == ["c-06-tick.ms"]
    assert load_manifest(manifest)[0].sha256 == entry.sha256
    assert pin(root, manifest) == []
    with pytest.raises(SourceError, match="is not in the handoff"):
        pin(tmp_path / "elsewhere", manifest)


# ---- The command line -------------------------------------------------------------------------


def _cli(tmp_path: Path, *extra: str) -> list[str]:
    root, entry = _handoff(tmp_path)
    manifest = _write_manifest(
        tmp_path / "m.json", {"c-06-tick.ms": {**GOOD, "sha256": entry.sha256}}
    )
    version = tmp_path / "HANDOFF_VERSION"
    version.write_text("v1\n", encoding="utf-8")
    return [
        str(root),
        str(tmp_path / "out"),
        "--manifest",
        str(manifest),
        "--version-file",
        str(version),
        *extra,
    ]


def test_main_writes_the_baselines(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert crop_handoff.main(_cli(tmp_path)) == 0
    assert "wrote 1 baselines" in capsys.readouterr().out
    assert (tmp_path / "out" / "v1" / "c-06-tick-ms.png").is_file()


def test_main_can_select_entries_and_rejects_unknown_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert crop_handoff.main(_cli(tmp_path, "--only", "c-06-tick.ms")) == 0
    assert crop_handoff.main(_cli(tmp_path, "--only", "nope")) == 1
    assert "not in the manifest: nope" in capsys.readouterr().err


def test_main_pins_first_when_asked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = _cli(tmp_path, "--pin")
    manifest = Path(argv[argv.index("--manifest") + 1])
    _write_manifest(manifest, {"c-06-tick.ms": {**GOOD, "sha256": "0" * 64}})
    assert crop_handoff.main(argv) == 0
    assert "pinned c-06-tick.ms" in capsys.readouterr().out


def test_main_reports_a_missing_source_and_can_skip_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = _cli(tmp_path)
    argv[0] = str(tmp_path / "elsewhere")
    assert crop_handoff.main(argv) == 1
    assert "is not in the handoff" in capsys.readouterr().err
    assert crop_handoff.main([*argv, "--skip-missing"]) == 0


# ---- Baseline fetch ---------------------------------------------------------------------------


def _source(tmp_path: Path) -> Path:
    root, entry = _handoff(tmp_path)
    source = tmp_path / "source"
    crop_all(root, source, [entry], "v1")
    return source


def test_fetch_copies_one_version_and_removes_the_rest(tmp_path: Path) -> None:
    source = _source(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "stale.png").write_bytes(b"old")
    assert baselines.fetch(str(source), dest, "v1") == ["c-06-tick.ms"]
    assert sorted(p.name for p in dest.glob("*.png")) == ["c-06-tick-ms.png"]


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        ("bucket", "bucket sources are not wired"),
        ("no_version", "no baselines for handoff version"),
        ("wrong_index", "the index is for"),
        ("missing_file", "is missing"),
        ("tampered", "does not match the index"),
    ],
)
def test_fetch_refuses_what_it_cannot_trust(tmp_path: Path, setup: str, message: str) -> None:
    source = _source(tmp_path)
    arg = str(source)
    if setup == "bucket":
        arg = "s3://abacus-shared-design-baselines/design"
    elif setup == "no_version":
        arg = str(tmp_path / "empty")
    elif setup == "wrong_index":
        index = source / "v1" / "index.json"
        index.write_text(json.dumps({"handoff_version": "v0", "entries": {}}), encoding="utf-8")
    elif setup == "missing_file":
        (source / "v1" / "c-06-tick-ms.png").unlink()
    elif setup == "tampered":
        (source / "v1" / "c-06-tick-ms.png").write_bytes(b"not the crop")
    with pytest.raises(baselines.BaselineError, match=message):
        baselines.fetch(arg, tmp_path / "dest", "v1")


def test_fetch_main(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    version = tmp_path / "HANDOFF_VERSION"
    version.write_text("v1\n", encoding="utf-8")
    argv = ["--dest", str(tmp_path / "dest"), "--version-file", str(version)]
    monkeypatch.delenv(baselines.SOURCE_ENV, raising=False)
    assert baselines.main(argv) == 1
    assert baselines.SOURCE_ENV in capsys.readouterr().err
    monkeypatch.setenv(baselines.SOURCE_ENV, str(source))
    assert baselines.main(argv) == 0
    assert "fetched 1 baselines" in capsys.readouterr().out
    monkeypatch.setenv(baselines.SOURCE_ENV, str(tmp_path / "empty"))
    assert baselines.main(argv) == 1
    assert "no baselines" in capsys.readouterr().err
